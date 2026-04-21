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
            # Use Quartz Window Services to get the title of the frontmost window of the frontmost app.
            try:
                from AppKit import NSWorkspace
                from Quartz import (
                    CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly,
                    kCGNullWindowID, kCGWindowListExcludeDesktopElements
                )
                
                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                if not app:
                    return ""
                
                pid = app.processIdentifier()
                # Get all on-screen windows
                window_list = CGWindowListCopyWindowInfo(
                    kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
                    kCGNullWindowID
                )
                
                for window in window_list:
                    if window.get("kCGWindowOwnerPID") == pid:
                        # The first window in the list for this PID is usually the frontmost one.
                        # Some apps (like Chrome) might have "invisible" windows, but
                        # kCGWindowLayer 0 is typically the main window layer.
                        if window.get("kCGWindowLayer") == 0:
                            return window.get("kCGWindowName", "")
                return ""
            except Exception:
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


# Terminal process names (used to identify terminal windows).
_TERMINAL_APPS = {
    # Windows
    "windowsterminal.exe", "wt.exe", "powershell.exe", "pwsh.exe",
    "cmd.exe", "conhost.exe",
    # macOS
    "terminal", "iterm2", "warp",
    # Linux
    "gnome-terminal-server", "konsole", "xfce4-terminal", "alacritty",
    "wezterm-gui", "kitty", "tilix",
}

# === CANONICAL WHITELIST ===
# AI coding assistant keywords matched in window titles and process names.
# Other scripts (install.ps1, install.sh, stop-voice.ps1, stop-voice.sh)
# duplicate this list for process detection — keep them in sync when adding
# new tools.
_AI_TITLE_KEYWORDS = ("claude", "gemini", "aider", "codex", "copilot")


def _is_voice_target(pid: int) -> bool:
    """Determine whether the foreground window is a valid voice target.

    Returns True when the user is actively interacting with an AI coding
    assistant — not in a plain terminal doing general shell work.

    Logic:
      1. If the foreground process itself is Claude (claude.exe) → yes.
      2. If the foreground is a terminal app → check window title for AI
         agent keywords (title reflects the active tab).
      3. If it's a multi-process Electron app (VS Code, Claude Desktop) →
         check process tree for claude AND verify title.
    """
    if not pid:
        return False

    root_pid = _find_app_root(pid)
    is_multi_process = (root_pid != pid)

    try:
        fg_proc = psutil.Process(pid)
        fg_name = (fg_proc.name() or "").lower()
    except psutil.NoSuchProcess:
        return False

    # Check 1: foreground IS a Claude-like process directly (Claude Desktop).
    if fg_name in ("claude", "claude.exe"):
        return True

    # Check 2: foreground is a terminal → title must contain an AI keyword.
    is_terminal = fg_name in _TERMINAL_APPS
    if not is_terminal and is_multi_process:
        try:
            root_name = (psutil.Process(root_pid).name() or "").lower()
            is_terminal = root_name in _TERMINAL_APPS
        except psutil.NoSuchProcess:
            pass

    if is_terminal:
        title = _get_foreground_title()
        title_lower = title.lower()

        # Claude Code uses braille spinner chars (U+2800–U+28FF) in title.
        if title and 0x2800 <= ord(title[0]) <= 0x28FF:
            return True

        # Explicit AI keyword in title.
        if any(kw in title_lower for kw in _AI_TITLE_KEYWORDS):
            return True

        # If title looks like a default shell prompt → definitely not AI.
        _SHELL_PREFIXES = (
            "windows powershell", "powershell", "pwsh", "cmd",
            "c:\\", "d:\\", "~", "bash", "zsh", "fish",
            "administrator:",
        )
        if any(title_lower.startswith(p) for p in _SHELL_PREFIXES):
            return False

        # Title is something else (e.g. a project/topic name set by an AI
        # CLI). Fall back to process-tree check.
        try:
            root = psutil.Process(root_pid)
            for child in root.children(recursive=True):
                if _looks_like_cc(child):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

    # Check 3: any non-terminal app — walk the process tree for an AI agent.
    # Covers Electron apps (VS Code, Claude Desktop) regardless of whether
    # the foreground PID is the root or a renderer subprocess.  This runs
    # in a background thread so the LL hook callback is never blocked.
    try:
        root = psutil.Process(root_pid)
        if _looks_like_cc(root):
            return True
        for child in root.children(recursive=True):
            if _looks_like_cc(child):
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    return False


if config.IS_WIN:
    # Windows: background thread to avoid LL hook 300ms timeout.
    _bg_result = {"is_cc": False}

    def _focus_monitor_loop():
        while True:
            try:
                pid = _get_foreground_pid()
                _bg_result["is_cc"] = _is_voice_target(pid) if pid else False
            except Exception:
                _bg_result["is_cc"] = False
            time.sleep(config.FOCUS_CACHE_TTL_SEC)

    threading.Thread(target=_focus_monitor_loop, daemon=True).start()

    def is_claude_code_focused() -> bool:
        return _bg_result["is_cc"]

else:
    # macOS / Linux: inline check is fine (pynput has no timeout limit).
    # Quartz/AppKit title APIs need the calling thread's context, so a
    # background thread would get empty titles and break whitelist filtering.
    _cache = {"ts": 0.0, "key": None, "is_cc": False}
    _cache_lock = threading.Lock()

    def is_claude_code_focused() -> bool:
        key = _get_foreground_key()
        if not key:
            return False
        now = time.time()
        with _cache_lock:
            if (now - _cache["ts"] < config.FOCUS_CACHE_TTL_SEC
                    and _cache["key"] == key):
                return _cache["is_cc"]
        pid = _get_foreground_pid()
        is_cc = _is_voice_target(pid) if pid else False
        with _cache_lock:
            _cache.update({"ts": now, "key": key, "is_cc": is_cc})
        return is_cc
