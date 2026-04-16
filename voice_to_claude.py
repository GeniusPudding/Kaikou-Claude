"""Entry point for the Claude Code Chinese voice bridge.

All substantive logic lives in the :mod:`voice_bridge` package; this file
only sets up stdio redirection (so the daemon survives being launched by
pythonw / nohup with detached stdout/stderr) and then dispatches into
``voice_bridge.runner.main``.
"""

import os
import sys
import tempfile


def _attach_log():
    """Redirect None stdout/stderr to a rolling log file.

    When the daemon is launched by pythonw.exe (Windows) or nohup
    (macOS/Linux) stdin/stdout/stderr may be closed or point to /dev/null.
    Swap in a shared log file so print() calls continue to work and show up
    in %TEMP%/claude-voice.log.
    """
    log_path = os.path.join(tempfile.gettempdir(), "claude-voice.log")
    if sys.stdout is None:
        sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    _attach_log()
    from voice_bridge import main
    sys.exit(main())
