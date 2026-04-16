"""macOS / Linux hotkey loop — F9 hold-to-talk via pynput.

pynput cannot selectively suppress a typing key portably without breaking
IME toggles and editor shortcuts, so Space is left untouched on non-Windows
platforms. F9 is plenty: it is not used for text input on any common
keyboard layout, so no conflict, no re-injection, no state machine needed.

macOS users must grant the terminal (or the Python binary) Accessibility
permission the first time so pynput can observe global key events. Linux
users need an X11 session (or XWayland) for pynput's keyboard grabbing.
"""

import threading

from pynput import keyboard as kb

from .. import audio
from ..focus import is_claude_code_focused

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
