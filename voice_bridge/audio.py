"""Audio capture, Whisper transcription, and paste-and-submit.

Kept fully platform-agnostic: recording goes through sounddevice, the model
comes from faster-whisper, and the paste step uses pyperclip + a cross-
platform pynput Controller. The hotkey backends call :func:`start_recording`
and :func:`stop_and_submit` regardless of OS.
"""

import threading
import time

import numpy as np
import pyperclip
import sounddevice as sd
from pynput import keyboard as kb

from . import config

try:
    import winsound  # Windows-only, used for quick audible feedback
except ImportError:
    winsound = None


_kb_ctrl = kb.Controller()
_state = {"recording": False, "frames": [], "stream": None}
_model = None
_lock = threading.Lock()

# Model-resident-on-GPU tracking. On CUDA-backed daemons the underlying
# ctranslate2 Whisper instance can be swapped to CPU RAM after a period of
# inactivity so other GPU workloads (training, etc.) are not blocked.
# "loaded"  – weights live on the configured device, ready for transcribe
# "swapped" – weights kicked off the GPU into CPU RAM via unload_model(to_cpu=True)
_model_state = "loaded"
_model_device = None  # actual device the model ended up on after init
_model_lock = threading.RLock()
_idle_timer = None  # threading.Timer when scheduled


def load_model():
    """Instantiate the faster-whisper model once at startup.

    Falls back to CPU/small if a CUDA load fails (e.g. driver mismatch).
    """
    global _model, _model_device
    from faster_whisper import WhisperModel

    t0 = time.time()
    try:
        _model = WhisperModel(config.MODEL_SIZE, device=config.DEVICE, compute_type=config.COMPUTE_TYPE)
        used_device = config.DEVICE
        used_model = config.MODEL_SIZE
    except Exception as e:
        if config.DEVICE == "cuda":
            print(f"× CUDA 載入失敗({e}),回退 CPU+small", flush=True)
            _model = WhisperModel("small", device="cpu", compute_type="int8")
            used_device = "cpu"
            used_model = "small"
        else:
            raise
    _model_device = used_device
    print(f"✓ 模型就緒({time.time() - t0:.1f}s, {used_device}, {used_model})", flush=True)
    if _model_device == "cuda" and config.IDLE_UNLOAD_SEC > 0:
        print(
            f"VRAM 閒置自動釋放:{config.IDLE_UNLOAD_SEC:.0f}s 沒講話就把權重搬回 CPU RAM",
            flush=True,
        )
        _schedule_idle_unload()


def _swap_to_cpu():
    """Move weights from GPU to CPU RAM (fast to reload).

    Runs from the idle Timer thread; no-op if model is already swapped or
    is not on cuda in the first place.
    """
    global _model_state, _idle_timer
    with _model_lock:
        _idle_timer = None
        if _model is None or _model_device != "cuda" or _model_state != "loaded":
            return
        try:
            _model.model.unload_model(to_cpu=True)
            _model_state = "swapped"
            print("↓ 閒置,VRAM 已釋放(權重暫存於 CPU RAM)", flush=True)
        except Exception as e:
            print(f"× VRAM 釋放失敗: {e}", flush=True)


def _ensure_loaded():
    """Swap weights back to the configured device if currently on CPU RAM."""
    with _model_lock:
        global _model_state
        if _model is None or _model_state == "loaded":
            return
        t0 = time.time()
        try:
            _model.model.load_model()
            _model_state = "loaded"
            print(f"↑ VRAM 重載({time.time() - t0:.1f}s)", flush=True)
        except Exception as e:
            print(f"× VRAM 重載失敗: {e}", flush=True)


def _cancel_idle_unload():
    global _idle_timer
    with _model_lock:
        if _idle_timer is not None:
            _idle_timer.cancel()
            _idle_timer = None


def _schedule_idle_unload():
    """Reset the inactivity timer that triggers _swap_to_cpu."""
    global _idle_timer
    if _model_device != "cuda" or config.IDLE_UNLOAD_SEC <= 0:
        return
    with _model_lock:
        if _idle_timer is not None:
            _idle_timer.cancel()
        _idle_timer = threading.Timer(config.IDLE_UNLOAD_SEC, _swap_to_cpu)
        _idle_timer.daemon = True
        _idle_timer.start()


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
    # User is interacting again — keep the model on GPU for the duration of
    # this round; new unload timer will be scheduled after transcription.
    _cancel_idle_unload()
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
    print("● 錄音中...", flush=True)


def _paste_and_submit(text: str):
    payload = f"{text}{config.VOICE_MARKER}" if config.VOICE_MARKER else text
    saved = ""
    try:
        saved = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(payload)
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
            _ensure_loaded()
            segments, _info = _model.transcribe(
                audio_f32, language=config.LANGUAGE, beam_size=1, vad_filter=True,
            )
            text = "".join(seg.text for seg in segments).strip()
    except Exception as e:
        print(f"× 轉錄失敗: {e}", flush=True)
        _schedule_idle_unload()
        return

    if not text:
        print("× 轉錄結果為空", flush=True)
        _schedule_idle_unload()
        return
    print(f"→ {text}", flush=True)
    _paste_and_submit(text)
    _beep(1200, 70)
    _schedule_idle_unload()


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
    _schedule_idle_unload()


def inject_key(key):
    """Send a key press/release through pynput (marked as injected on Windows
    so our own LL hook ignores it)."""
    try:
        _kb_ctrl.press(key)
        _kb_ctrl.release(key)
    except Exception as e:
        print(f"× inject_key({key}): {e}", flush=True)
