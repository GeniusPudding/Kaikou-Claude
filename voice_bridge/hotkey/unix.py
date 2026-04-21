"""macOS / Linux hotkey loops via pynput.

macOS — Cmd (hold alone ≥ threshold):
    Hold Cmd without pressing any other key to record. If another key is
    pressed while Cmd is held the recording is cancelled (it was a shortcut
    like Cmd+C). Short Cmd tap does nothing.

Linux — F9 (hold):
    Simple hold-to-talk. No conflict with typing.

Both platforms require the terminal (or Python binary) to be granted
Accessibility permission on macOS, and an X11 session on Linux.
"""

import threading

from pynput import keyboard as kb

from .. import audio, config
from ..focus import is_claude_code_focused

# ---------------------------------------------------------------------------
# macOS: Cmd hold-to-talk (with shortcut cancellation)
# ---------------------------------------------------------------------------
if config.IS_MAC:
    _CMD_KEYS = {kb.Key.cmd, kb.Key.cmd_l, kb.Key.cmd_r}

    _state = {
        "state": "idle",   # idle | waiting | recording
        "timer": None,
        "busy": False,     # True while paste is in progress (ignore own keystrokes)
    }
    _lock = threading.Lock()

    def _upgrade_to_recording():
        with _lock:
            if _state["state"] != "waiting":
                return
            _state["state"] = "recording"
        threading.Thread(target=audio.start_recording, daemon=True).start()

    def _on_press(key):
        with _lock:
            if _state["busy"]:
                return
            state = _state["state"]

        if key in _CMD_KEYS:
            with _lock:
                if _state["state"] != "idle":
                    return
                if not is_claude_code_focused():
                    return
                _state["state"] = "waiting"
                t = threading.Timer(config.HOLD_THRESHOLD_SEC, _upgrade_to_recording)
                _state["timer"] = t
                t.start()
            return

        # Any non-Cmd key while waiting/recording → cancel (user is doing a shortcut)
        if state in ("waiting", "recording"):
            with _lock:
                if _state["timer"]:
                    _state["timer"].cancel()
                    _state["timer"] = None
                was_recording = (_state["state"] == "recording")
                _state["state"] = "idle"
            if was_recording:
                # Discard partial recording silently
                threading.Thread(target=audio.stop_and_submit, daemon=True).start()

    def _on_release(key):
        if key not in _CMD_KEYS:
            return
        with _lock:
            if _state["busy"]:
                return
            state = _state["state"]
            if state == "waiting":
                if _state["timer"]:
                    _state["timer"].cancel()
                    _state["timer"] = None
                _state["state"] = "idle"
                return
            if state == "recording":
                _state["state"] = "idle"
                _state["busy"] = True

        if state == "recording":
            def _finish():
                try:
                    audio.stop_and_submit()
                finally:
                    with _lock:
                        _state["busy"] = False
            threading.Thread(target=_finish, daemon=True).start()

    def run_loop():
        print("✓ pynput keyboard listener 已安裝(Cmd hold-to-talk)", flush=True)
        with kb.Listener(on_press=_on_press, on_release=_on_release) as listener:
            listener.join()

# ---------------------------------------------------------------------------
# Linux: F9 hold-to-talk
# ---------------------------------------------------------------------------
else:
    _state = {"down": False, "busy": False}
    _lock = threading.Lock()

    def _on_press(key):
        if key != kb.Key.f9:
            return
        with _lock:
            if _state["down"] or _state["busy"]:
                return
            if not is_claude_code_focused():
                return
            _state["down"] = True
        threading.Thread(target=audio.start_recording, daemon=True).start()

    def _on_release(key):
        if key != kb.Key.f9:
            return
        with _lock:
            if not _state["down"]:
                return
            _state["down"] = False
            _state["busy"] = True

        def _finish():
            try:
                audio.stop_and_submit()
            finally:
                with _lock:
                    _state["busy"] = False

        threading.Thread(target=_finish, daemon=True).start()

    def run_loop():
        print("✓ pynput keyboard listener 已安裝(F9 hold-to-talk)", flush=True)
        with kb.Listener(on_press=_on_press, on_release=_on_release) as listener:
            listener.join()
