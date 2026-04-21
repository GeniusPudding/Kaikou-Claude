#!/usr/bin/env bash
# Idempotent launcher used by Claude Code SessionStart hook (macOS / Linux).
# If daemon is already alive, does nothing. Otherwise launches it.

set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
voice_dir="$(cd "$script_dir/.." && pwd)"
tmp_dir="${TMPDIR:-/tmp}"
pid_file="$tmp_dir/claude-voice.pid"
log_file="$tmp_dir/claude-voice.log"
python_bin="$voice_dir/.venv/bin/python"
script="$voice_dir/voice_to_claude.py"

# Platform-specific message: Cmd on macOS, F9 on Linux.
if [[ "$(uname -s)" == "Darwin" ]]; then
    msg='{"systemMessage":"\u4e2d\u6587\u8a9e\u97f3\u5df2\u555f\u52d5 \u2014 \u6309\u4f4f Cmd \u8b1b\u4e2d\u6587,\u653e\u958b\u81ea\u52d5\u9001\u51fa(Cmd+\u5176\u4ed6\u9375=\u6b63\u5e38\u5feb\u6377\u9375)"}'
else
    msg='{"systemMessage":"\u4e2d\u6587\u8a9e\u97f3\u5df2\u555f\u52d5 \u2014 \u6309\u4f4f F9 \u8b1b\u4e2d\u6587,\u653e\u958b\u81ea\u52d5\u9001\u51fa"}'
fi

# Already running?
if [[ -f "$pid_file" ]]; then
    existing=$(head -n 1 "$pid_file" 2>/dev/null || true)
    if [[ "$existing" =~ ^[0-9]+$ ]] && kill -0 "$existing" 2>/dev/null; then
        echo "$msg"
        exit 0
    fi
fi

if [[ ! -x "$python_bin" ]]; then
    echo '{"systemMessage":"[kaikou-claude] venv not found. Run install.sh first."}'
    exit 1
fi

nohup "$python_bin" "$script" >>"$log_file" 2>&1 &
disown >/dev/null 2>&1 || true

echo "$msg"
exit 0
