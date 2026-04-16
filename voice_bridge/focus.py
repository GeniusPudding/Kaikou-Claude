"""Foreground-window detection for Claude Code.

Exposes a single entry point, :func:`is_claude_code_focused`, which returns
True when the process tree rooted at the OS-foreground window contains any
process that looks like Claude Code.

The OS-specific step is getting a PID for the foreground window:
  * Windows — GetForegroundWindow + GetWindowThreadProcessId via ctypes.
  * macOS   — NSWorkspace.frontmostApplication (pyobjc).
  * Linux   — xdotool getactivewindow (X11 only; Wayland falls back to 0).

Results are cached with a short TTL so holding a key generates at most one
expensive tree walk per refresh window.
"""

import threading
import time

import psutil

from . import config


def _build_get_foreground_pid():
    if config.IS_WIN:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
        ]

        def get_pid():
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return 0
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return int(pid.value or 0)

        def get_key():
            # hwnd is a stable handle per foreground window.
            return int(user32.GetForegroundWindow() or 0)

        return get_pid, get_key

    if config.IS_MAC:
        def get_pid():
            try:
                from AppKit import NSWorkspace
                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                return int(app.processIdentifier()) if app else 0
            except Exception:
                return 0

        def get_key():
            return get_pid()

        return get_pid, get_key

    # Linux / BSD — X11 via xdotool. Wayland returns 0 and focus detection
    # silently fails; that is acceptable as a fallback since the hotkey loop
    # keeps working, just without "only-when-CC-is-focused" gating.
    import subprocess

    def get_pid():
        try:
            out = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowpid"],
                stderr=subprocess.DEVNULL, timeout=0.3, text=True,
            ).strip()
            return int(out) if out else 0
        except (FileNotFoundError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired, ValueError):
            return 0

    def get_key():
        return get_pid()

    return get_pid, get_key


_get_foreground_pid, _get_foreground_key = _build_get_foreground_pid()


def _looks_like_cc(proc: psutil.Process) -> bool:
    try:
        name = (proc.name() or "").lower()
        if name in ("claude", "claude.exe"):
            return True
        try:
            cmd = " ".join(proc.cmdline() or []).lower()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            cmd = ""
        if "claude" in cmd and (name.startswith("node") or name.startswith("claude")):
            return True
        if "claude-code" in cmd or "@anthropic-ai/claude" in cmd:
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return False


def _fg_tree_has_claude(pid: int) -> bool:
    if not pid:
        return False
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False
    if _looks_like_cc(root):
        return True
    try:
        for child in root.children(recursive=True):
            if _looks_like_cc(child):
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return False


_cache = {"ts": 0.0, "key": None, "is_cc": False}
_lock = threading.Lock()


def is_claude_code_focused() -> bool:
    key = _get_foreground_key()
    if not key:
        return False
    now = time.time()
    with _lock:
        if (now - _cache["ts"] < config.FOCUS_CACHE_TTL_SEC
                and _cache["key"] == key):
            return _cache["is_cc"]
    is_cc = _fg_tree_has_claude(_get_foreground_pid())
    with _lock:
        _cache.update({"ts": now, "key": key, "is_cc": is_cc})
    return is_cc
