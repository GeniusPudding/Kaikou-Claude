"""Windows hotkey loop — low-level keyboard hook with selective Space handling.

Space (when Claude Code is focused and no modifier is held):
  * tap (< HOLD_THRESHOLD_SEC) is replayed as a normal space character so
    typing feels native;
  * hold (>= HOLD_THRESHOLD_SEC) starts recording; on release, the injected
    leading space is erased with a Backspace and the transcription is
    pasted + submitted.

F9 (when Claude Code is focused): plain hold-to-talk, no tap fallback.

Space with any Shift/Ctrl/Alt/Win modifier is passed through untouched so
IME toggles and keyboard shortcuts keep working.
"""

import ctypes
import threading
import time
from ctypes import wintypes

from pynput import keyboard as kb

from .. import audio, config
from ..focus import is_claude_code_focused

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
HC_ACTION = 0
LLKHF_INJECTED = 0x10
VK_SPACE = 0x20
VK_F9 = 0x78
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN = 0x5B, 0x5C


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


_LRESULT = ctypes.c_ssize_t
_HOOKPROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
_user32.CallNextHookEx.restype = _LRESULT
_user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _any_modifier_pressed():
    return any(
        _user32.GetAsyncKeyState(vk) & 0x8000
        for vk in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
    )


_hk = {
    "pressed": set(),
    "state": "idle",   # idle | space_waiting | space_recording | f9_recording
    "timer": None,
}
_hk_lock = threading.Lock()


def _upgrade_to_recording():
    with _hk_lock:
        if _hk["state"] != "space_waiting":
            return
        _hk["state"] = "space_recording"
    threading.Thread(target=audio.start_recording, daemon=True).start()


def _handle_space_down():
    with _hk_lock:
        if _hk["state"] != "idle":
            return
        _hk["state"] = "space_waiting"
        t = threading.Timer(config.HOLD_THRESHOLD_SEC, _upgrade_to_recording)
        _hk["timer"] = t
        t.start()
    threading.Thread(target=audio.inject_key, args=(kb.Key.space,), daemon=True).start()


def _handle_space_up():
    with _hk_lock:
        st = _hk["state"]
        if st == "space_waiting":
            if _hk["timer"]:
                _hk["timer"].cancel()
            _hk["state"] = "idle"
            return
        if st == "space_recording":
            _hk["state"] = "idle"
            threading.Thread(target=_transcribe_with_backspace, daemon=True).start()


def _transcribe_with_backspace():
    audio.inject_key(kb.Key.backspace)
    time.sleep(0.02)
    audio.stop_and_submit()


def _handle_f9_down():
    with _hk_lock:
        if _hk["state"] != "idle":
            return
        _hk["state"] = "f9_recording"
    threading.Thread(target=audio.start_recording, daemon=True).start()


def _handle_f9_up():
    with _hk_lock:
        if _hk["state"] != "f9_recording":
            return
        _hk["state"] = "idle"
    threading.Thread(target=audio.stop_and_submit, daemon=True).start()


def _ll_kb_proc(nCode, wParam, lParam):
    if nCode != HC_ACTION:
        return _user32.CallNextHookEx(None, nCode, wParam, lParam)
    kbs = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT))[0]
    if kbs.flags & LLKHF_INJECTED:
        return _user32.CallNextHookEx(None, nCode, wParam, lParam)

    vk = kbs.vkCode
    is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
    is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

    if vk == VK_F9:
        if not is_claude_code_focused():
            return _user32.CallNextHookEx(None, nCode, wParam, lParam)
        if is_down:
            if vk not in _hk["pressed"]:
                _hk["pressed"].add(vk)
                _handle_f9_down()
            return 1
        if is_up:
            _hk["pressed"].discard(vk)
            _handle_f9_up()
            return 1

    if vk == VK_SPACE:
        if not is_claude_code_focused() or _any_modifier_pressed():
            return _user32.CallNextHookEx(None, nCode, wParam, lParam)
        if is_down:
            if vk not in _hk["pressed"]:
                _hk["pressed"].add(vk)
                _handle_space_down()
            return 1
        if is_up:
            _hk["pressed"].discard(vk)
            _handle_space_up()
            return 1

    return _user32.CallNextHookEx(None, nCode, wParam, lParam)


# Keep a reference to the ctypes callback so it isn't garbage-collected
# while the hook is live.
_HOOK_PROC_REF = _HOOKPROC(_ll_kb_proc)


def run_loop():
    hmod = _kernel32.GetModuleHandleW(None)
    hook_id = _user32.SetWindowsHookExW(WH_KEYBOARD_LL, _HOOK_PROC_REF, hmod, 0)
    if not hook_id:
        err = ctypes.get_last_error()
        print(f"× SetWindowsHookExW failed: {err}", flush=True)
        return
    print("✓ LL keyboard hook 已安裝", flush=True)
    msg = wintypes.MSG()
    try:
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        _user32.UnhookWindowsHookEx(hook_id)
