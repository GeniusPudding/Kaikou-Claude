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


def load_model():
    """Instantiate the faster-whisper model once at startup.

    Falls back to CPU/small if a CUDA load fails (e.g. driver mismatch).
    """
    global _model
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
    print(f"✓ 模型就緒({time.time() - t0:.1f}s, {used_device}, {used_model})", flush=True)


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
    time.sleep(0.05)
    paste_modifier = kb.Key.cmd if config.IS_MAC else kb.Key.ctrl
    _kb_ctrl.press(paste_modifier)
    _kb_ctrl.press("v")
    _kb_ctrl.release("v")
    _kb_ctrl.release(paste_modifier)
    time.sleep(0.12)
    if config.AUTO_SUBMIT:
        _kb_ctrl.press(kb.Key.enter)
        _kb_ctrl.release(kb.Key.enter)
    time.sleep(0.25)
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
        segments, _info = _model.transcribe(
            audio_f32, language=config.LANGUAGE, beam_size=5, vad_filter=True,
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


def inject_key(key):
    """Send a key press/release through pynput (marked as injected on Windows
    so our own LL hook ignores it)."""
    try:
        _kb_ctrl.press(key)
        _kb_ctrl.release(key)
    except Exception as e:
        print(f"× inject_key({key}): {e}", flush=True)
