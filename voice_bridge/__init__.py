"""Chinese voice bridge for Claude Code — package root.

The public entry point is :func:`voice_bridge.runner.main`; the root
``voice_to_claude.py`` script just imports and invokes it.
"""

from .runner import main

__all__ = ["main"]
