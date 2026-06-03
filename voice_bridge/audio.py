"""Audio capture, Whisper transcription, and paste-and-submit.

Kept fully platform-agnostic: recording goes through sounddevice, the model
comes from faster-whisper, and the paste step uses pyperclip + a cross-
platform pynput Controller. The hotkey backends call :func:`start_recording`
and :func:`stop_and_submit` regardless of OS.

Model lifecycle
---------------
On CUDA systems the daemon manages two Whisper instances:

* ``_primary``   — the high-quality CUDA model used by default
  (large-v3-turbo + float16). Resides in VRAM.
* ``_fallback``  — a small CPU model (small + int8), lazily loaded the
  first time the user releases the GPU to another workload.

A background watcher polls a sentinel file (written by ``scripts/release-gpu``
and removed by ``scripts/acquire-gpu``); when the sentinel appears, the
daemon unloads the primary from the GPU and switches transcription to the
CPU fallback so voice keeps working — just slower — while the user trains,
runs inference, etc. When the sentinel disappears, the primary is reloaded
on the GPU and becomes active again.

CPU-only systems (e.g. macOS without CUDA) load only ``_primary`` (small +
int8 on CPU) and the watcher is not started; release/acquire are a no-op
because there is no GPU to release in the first place.
"""

import os
import threading
import time

import numpy as np
import pyperclip
import sounddevice as sd
from pynput import keyboard as kb

from . import config, focus

try:
    import winsound  # Windows-only, used for quick audible feedback
except ImportError:
    winsound = None


_kb_ctrl = kb.Controller()
_state = {"recording": False, "frames": [], "stream": None}
_lock = threading.Lock()
# Window that had focus when the user pressed the hotkey — Ctrl+V/Cmd+V
# is sent to whatever window is foreground at paste time, so we restore
# this one before pasting in case the user switched apps mid-recording.
_target_handle = None
# Hotkey backends snapshot the foreground window at key-down (before any
# hold delay) and stash it here. start_recording prefers it over a fresh
# live capture so the paste target is the window that was active when
# the user *initiated* the press, not the one that happens to be active
# 250ms later if they alt-tabbed.
_pending_target = None


def set_pending_target(handle):
    """Called from hotkey backends at key-down to snapshot the target."""
    global _pending_target
    _pending_target = handle

# Model slots and active selector. Only ever access via the helpers below
# under _model_lock so the sentinel watcher and the hotkey transcribe path
# don't trip over each other while we swap WhisperModel instances.
_primary = None         # WhisperModel; CUDA turbo when available, else CPU small
_fallback = None        # WhisperModel; CPU small. None until first release.
_active = "primary"     # "primary" | "fallback"
_primary_device = None  # "cuda" | "cpu" — what _primary was actually instantiated on
_model_lock = threading.RLock()
_watcher_stop = threading.Event()


def _active_model():
    """Return the currently-active WhisperModel under the model lock."""
    if _active == "fallback" and _fallback is not None:
        return _fallback
    return _primary


def load_model():
    """Instantiate the primary model and (on CUDA) start the sentinel watcher.

    If the release sentinel is already present at startup *and* we'd normally
    target CUDA, we skip the primary load entirely and boot straight into
    fallback (CPU small + int8). This avoids briefly allocating VRAM the user
    has explicitly freed for another workload; primary is loaded later when
    ``acquire-gpu`` removes the sentinel.
    """
    global _primary, _primary_device, _active
    from faster_whisper import WhisperModel

    target_cuda = config.DEVICE == "cuda"
    sentinel_at_startup = target_cuda and os.path.exists(config.RELEASE_SENTINEL_PATH)

    if sentinel_at_startup:
        print(
            f"偵測到 release sentinel({config.RELEASE_SENTINEL_PATH}) → "
            "略過 primary,直接啟動 CPU fallback",
            flush=True,
        )
        _primary_device = "cuda"   # remember the intent; primary will load on acquire
        _ensure_fallback_loaded()
        if _fallback is None:
            raise RuntimeError("Failed to load CPU fallback model with release sentinel active")
        _active = "fallback"
        threading.Thread(target=_sentinel_watch_loop, daemon=True, name="release-watcher").start()
        return

    t0 = time.time()
    try:
        _primary = WhisperModel(config.MODEL_SIZE, device=config.DEVICE, compute_type=config.COMPUTE_TYPE)
        used_device = config.DEVICE
        used_model = config.MODEL_SIZE
    except Exception as e:
        if target_cuda:
            print(f"× CUDA 載入失敗({e}),回退 CPU+small", flush=True)
            _primary = WhisperModel("small", device="cpu", compute_type="int8")
            used_device = "cpu"
            used_model = "small"
        else:
            raise
    _primary_device = used_device
    print(f"✓ 模型就緒({time.time() - t0:.1f}s, {used_device}, {used_model})", flush=True)

    if _primary_device == "cuda":
        print(
            f"Release sentinel: {config.RELEASE_SENTINEL_PATH}  "
            "(run scripts/release-gpu to hand the GPU over)",
            flush=True,
        )
        threading.Thread(target=_sentinel_watch_loop, daemon=True, name="release-watcher").start()


def _ensure_fallback_loaded():
    """Load the small CPU fallback model lazily, the first time it's needed."""
    global _fallback
    if _fallback is not None:
        return
    from faster_whisper import WhisperModel
    t0 = time.time()
    try:
        _fallback = WhisperModel(
            config.FALLBACK_MODEL_SIZE, device="cpu", compute_type=config.FALLBACK_COMPUTE_TYPE,
        )
        print(
            f"↻ CPU fallback 模型已載入({config.FALLBACK_MODEL_SIZE} + "
            f"{config.FALLBACK_COMPUTE_TYPE}, {time.time() - t0:.1f}s)",
            flush=True,
        )
    except Exception as e:
        print(f"× CPU fallback 載入失敗: {e}", flush=True)
        _fallback = None


def _switch_to_fallback():
    """Move active transcription from CUDA primary to CPU fallback.

    No-op on CPU-only daemons (primary is already the small CPU model).
    """
    global _active
    with _model_lock:
        if _primary_device != "cuda":
            return
        if _active == "fallback":
            return
        _ensure_fallback_loaded()
        if _fallback is None:
            return  # load failed; stay on primary so user isn't dead in the water
        try:
            _primary.model.unload_model(to_cpu=False)
        except Exception as e:
            print(f"× 從 GPU 卸載 primary 失敗: {e}", flush=True)
            return
        _active = "fallback"
        print(
            "⇣ GPU 已釋放,語音改用 CPU(慢一點但仍可用)。"
            "訓練完跑 acquire-gpu 切回 CUDA。",
            flush=True,
        )


def _switch_to_primary():
    """Move active transcription back to the CUDA primary.

    Handles two cases:
      1. ``_primary`` already exists (daemon started normally, was later
         released): re-load the existing weights back onto the GPU
         (~1-2s — they're still cached in process memory).
      2. ``_primary`` is None (daemon started with the sentinel present
         and skipped the primary load): construct the model from disk
         now (~10-15s, first time only).
    """
    global _active, _primary
    with _model_lock:
        if _primary_device != "cuda":
            return
        if _active == "primary":
            return
        t0 = time.time()
        if _primary is None:
            from faster_whisper import WhisperModel
            try:
                _primary = WhisperModel(
                    config.MODEL_SIZE, device=config.DEVICE, compute_type=config.COMPUTE_TYPE,
                )
            except Exception as e:
                print(f"× primary 首次載入失敗,留在 CPU fallback: {e}", flush=True)
                return
        else:
            try:
                _primary.model.load_model()
            except Exception as e:
                print(f"× primary 重載到 GPU 失敗,留在 CPU fallback: {e}", flush=True)
                return
        _active = "primary"
        print(
            f"⇡ GPU 取回,切回 {config.MODEL_SIZE}({time.time() - t0:.1f}s)",
            flush=True,
        )


def _sentinel_watch_loop():
    """Background watcher that flips primary↔fallback on sentinel changes.

    Runs only on CUDA daemons. Polls every ``SENTINEL_POLL_SEC`` and only
    acts when the file's presence state changes, so a stale sentinel from
    before startup doesn't cause repeated switches.
    """
    last_present = os.path.exists(config.RELEASE_SENTINEL_PATH)
    while not _watcher_stop.wait(config.SENTINEL_POLL_SEC):
        present = os.path.exists(config.RELEASE_SENTINEL_PATH)
        if present == last_present:
            continue
        if present:
            _switch_to_fallback()
        else:
            _switch_to_primary()
        last_present = present


def _beep(freq, ms=90):
    if winsound is not None:
        try:
            winsound.Beep(freq, ms)
        except RuntimeError:
            pass


def _audio_cb(indata, frames_count, time_info, status):
    if _state["recording"]:
        _state["frames"].append(indata.copy())


def start_recording():
    global _target_handle, _pending_target
    # Prefer the snapshot taken at key-down by the hotkey backend; only
    # fall back to a live capture if it didn't set one (e.g. a code path
    # we didn't update). The key-down snapshot eliminates the 250ms gap
    # during which the user could have switched windows.
    if _pending_target is not None:
        _target_handle = _pending_target
        _pending_target = None
    else:
        _target_handle = focus.capture_target_window()
    with _lock:
        if _state["recording"]:
            return
        _state["frames"] = []
        _state["recording"] = True
        stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="int16",
            callback=_audio_cb,
        )
        stream.start()
        _state["stream"] = stream
    _beep(880)
    if _active == "fallback":
        print("● 錄音中...(GPU 已釋放,將用 CPU 轉錄)", flush=True)
    else:
        print("● 錄音中...", flush=True)


def _paste_and_submit(text: str):
    # Before doing anything destructive (clipboard write + key injection),
    # re-verify the captured target still belongs to an AI agent. If focus
    # detection had a stale-cache race at key-down — or the original window
    # has since been closed / replaced — the safest move is to drop the
    # paste rather than dump the transcription into someone's chat app.
    if _target_handle is not None and not focus.is_voice_target_handle(_target_handle):
        print(
            "⚠ 目的視窗已不是 AI agent,放棄貼上(避免污染其他輸入框)",
            flush=True,
        )
        print(f"   轉錄結果: {text}", flush=True)
        return

    payload = f"{text}{config.VOICE_MARKER}" if config.VOICE_MARKER else text
    saved = ""
    try:
        saved = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(payload)
    # Restore the window that was active when the user pressed the hotkey,
    # in case they switched apps while we were transcribing.
    if _target_handle is not None:
        try:
            focus.restore_target_window(_target_handle)
        except Exception as e:
            print(f"× 還原焦點失敗: {e}", flush=True)
        time.sleep(0.08)  # let the OS register the focus change before Ctrl+V
    else:
        time.sleep(0.1)
    paste_modifier = kb.Key.cmd if config.IS_MAC else kb.Key.ctrl
    _kb_ctrl.press(paste_modifier)
    _kb_ctrl.press("v")
    _kb_ctrl.release("v")
    _kb_ctrl.release(paste_modifier)
    time.sleep(0.15)
    if config.AUTO_SUBMIT:
        _kb_ctrl.press(kb.Key.enter)
        _kb_ctrl.release(kb.Key.enter)
    time.sleep(0.25)
    print("[paste] done", flush=True)
    try:
        pyperclip.copy(saved)
    except Exception:
        pass


def stop_and_submit():
    """Stop the active recording, transcribe, and paste + submit the text."""
    with _lock:
        if not _state["recording"]:
            return
        _state["recording"] = False
        stream = _state["stream"]
        _state["stream"] = None
        frames = _state["frames"]

    if stream is not None:
        stream.stop()
        stream.close()
    _beep(440)

    if not frames:
        print("× 沒錄到聲音", flush=True)
        return

    audio_i16 = np.concatenate(frames, axis=0).flatten()
    audio_f32 = audio_i16.astype(np.float32) / 32768.0

    print("… 轉錄中", flush=True)
    try:
        with _model_lock:
            model = _active_model()
            if model is None:
                print("× 沒有可用的轉錄模型", flush=True)
                return
            segments, _info = model.transcribe(
                audio_f32, language=config.LANGUAGE, beam_size=1, vad_filter=True,
            )
            text = "".join(seg.text for seg in segments).strip()
    except Exception as e:
        print(f"× 轉錄失敗: {e}", flush=True)
        return

    if not text:
        print("× 轉錄結果為空", flush=True)
        return
    print(f"→ {text}", flush=True)
    _paste_and_submit(text)
    _beep(1200, 70)


def discard_recording():
    """Stop the active recording and throw away the audio (no transcription)."""
    with _lock:
        if not _state["recording"]:
            return
        _state["recording"] = False
        stream = _state["stream"]
        _state["stream"] = None
    if stream is not None:
        stream.stop()
        stream.close()
    print("⏹ 錄音已作廢", flush=True)


def inject_key(key):
    """Send a key press/release through pynput (marked as injected on Windows
    so our own LL hook ignores it)."""
    try:
        _kb_ctrl.press(key)
        _kb_ctrl.release(key)
    except Exception as e:
        print(f"× inject_key({key}): {e}", flush=True)
