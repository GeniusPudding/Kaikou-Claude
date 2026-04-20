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


def _build_foreground_helpers():
    """Return three closures: (get_pid, get_key, get_title).

    * get_pid  — PID of the process that owns the foreground window.
    * get_key  — fast cache key that changes when the foreground changes.
    * get_title — text title of the foreground window (used to distinguish
      among multiple windows of the same Electron app).
    """
    if config.IS_WIN:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
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
            return int(user32.GetForegroundWindow() or 0)

        def get_title():
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value

        return get_pid, get_key, get_title

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

        def get_title():
            # NSWorkspace doesn't expose per-window title easily; skip.
            return ""

        return get_pid, get_key, get_title

    # Linux / BSD
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

    def get_title():
        try:
            return subprocess.check_output(
                ["xdotool", "getactivewindow", "getactivewindow", "--name"],
                stderr=subprocess.DEVNULL, timeout=0.3, text=True,
            ).strip()
        except Exception:
            return ""

    def get_key():
        return get_pid()

    return get_pid, get_key, get_title


_get_foreground_pid, _get_foreground_key, _get_foreground_title = _build_foreground_helpers()


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


def _find_app_root(pid: int) -> int:
    """Walk up the process tree as long as the parent has the same executable
    name, and return the topmost PID.

    This handles multi-process apps like Electron (VS Code, Claude Desktop)
    where the foreground window belongs to a renderer process but the Claude
    Code extension lives under a different branch of the same Code.exe tree.
    """
    try:
        proc = psutil.Process(pid)
        name = (proc.name() or "").lower()
    except psutil.NoSuchProcess:
        return pid
    root_pid = pid
    cur = proc
    for _ in range(20):
        try:
            parent = cur.parent()
            if parent is None:
                break
            if (parent.name() or "").lower() != name:
                break
            root_pid = parent.pid
            cur = parent
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break
    return root_pid


def _fg_tree_has_claude(pid: int) -> bool:
    if not pid:
        return False
    # For multi-process apps (Electron), walk up to the app root first so
    # we search the entire process tree, not just the renderer's subtree.
    root_pid = _find_app_root(pid)
    is_multi_process = (root_pid != pid)

    found = False
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return False
    if _looks_like_cc(root):
        found = True
    else:
        try:
            for child in root.children(recursive=True):
                if _looks_like_cc(child):
                    found = True
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not found:
        return False

    # When the app has multiple windows under one process tree (e.g. VS
    # Code with many windows, only one of which has Claude active), use the
    # window title as a secondary filter so voice doesn't fire in the wrong
    # window. Single-process terminals (WindowsTerminal, iTerm) skip this.
    if is_multi_process:
        title = _get_foreground_title().lower()
        if title and "claude" not in title:
            return False

    return True


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
