"""Hotkey backend — pick Windows LL-hook implementation or the portable
pynput F9 listener based on sys.platform.

Each backend exposes a single ``run_loop()`` that blocks until the process
is terminated.
"""

from .. import config

if config.IS_WIN:
    from .windows import run_loop
else:
    from .unix import run_loop

__all__ = ["run_loop"]
