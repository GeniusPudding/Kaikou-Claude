"""macOS / Linux hotkey loop — instant Cmd/F9 hold-to-talk.

macOS — Cmd (instant):
    1. Press Cmd → start recording immediately (if Claude is focused).
    2. During hold: if any other key is pressed (Cmd+C, Cmd+Tab, etc.)
       or focus is lost → mark as "cancelled".
    3. Release Cmd: if cancelled or held < 0.1s → discard recording.
       Otherwise → stop, transcribe, paste, submit.
    F9 also works as a backup hotkey.

Linux — F9 (hold):
    Simple hold-to-talk. No conflict with typing.

Both platforms require the terminal (or Python binary) to be granted
Accessibility permission on macOS, and an X11 session on Linux.
"""

import threading
import time

from pynput import keyboard as kb

from .. import audio, config
from ..focus import is_claude_code_focused

_CMD_KEYS = {kb.Key.cmd, kb.Key.cmd_l, kb.Key.cmd_r}
_TRIGGER_KEYS = _CMD_KEYS | {kb.Key.f9}

_state = {
    "mode": "idle",        # idle | recording
    "busy": False,         # True while paste in progress
    "cancelled": False,
    "start_time": 0.0,
}
_lock = threading.Lock()


def _check_focus_loop():
    """Background thread: cancel recording if focus leaves Claude."""
    while True:
        with _lock:
            if _state["mode"] != "recording":
                break
            if not is_claude_code_focused():
                _state["cancelled"] = True
                print("��� 焦點遺失，錄音已作廢", flush=True)
                break
        time.sleep(0.05)


def _on_press(key):
    with _lock:
        # During recording: any non-trigger key → cancel (it's a shortcut)
        if _state["mode"] == "recording" and key not in _TRIGGER_KEYS:
            _state["cancelled"] = True
            return
        if _state["mode"] != "idle" or _state["busy"]:
            return

    if key in _TRIGGER_KEYS:
        if not is_claude_code_focused():
            return
        with _lock:
            _state["mode"] = "recording"
            _state["cancelled"] = False
            _state["start_time"] = time.time()
        audio.start_recording()
        threading.Thread(target=_check_focus_loop, daemon=True).start()


def _on_release(key):
    if key not in _TRIGGER_KEYS:
        return
    with _lock:
        if _state["mode"] != "recording":
            return
        was_cancelled = _state["cancelled"]
        # Very short press (< 0.1s) = accidental tap, also discard
        if time.time() - _state["start_time"] < 0.1:
            was_cancelled = True
        _state["mode"] = "idle"

    if was_cancelled:
        threading.Thread(target=audio.discard_recording, daemon=True).start()
    else:
        with _lock:
            _state["busy"] = True

        def _finish():
            try:
                audio.stop_and_submit()
            finally:
                with _lock:
                    _state["busy"] = False

        threading.Thread(target=_finish, daemon=True).start()


def run_loop():
    if config.IS_MAC:
        print("✓ pynput listener 已安裝(Cmd / F9 hold-to-talk)", flush=True)
    else:
        print("✓ pynput listener 已安裝(F9 hold-to-talk)", flush=True)
    with kb.Listener(on_press=_on_press, on_release=_on_release) as listener:
        listener.join()
