#!/usr/bin/env bash
# Idempotent launcher used by Claude Code SessionStart hook (macOS / Linux).
# Resolves the repo root relative to this script so it works regardless of
# where the repo is cloned.

set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
voice_dir="$(cd "$script_dir/.." && pwd)"
tmp_dir="${TMPDIR:-/tmp}"
pid_file="$tmp_dir/claude-voice.pid"
sess_file="$tmp_dir/claude-voice.sessions"
log_file="$tmp_dir/claude-voice.log"
python_bin="$voice_dir/.venv/bin/python"
script="$voice_dir/voice_to_claude.py"

# ASCII-safe JSON with unicode escapes; the hook prints this to stdout so
# Claude Code can surface it as a systemMessage to the user.
msg='{"systemMessage":"\u4e2d\u6587\u8a9e\u97f3\u5df2\u555f\u52d5 \u2014 \u6309\u4f4f F9 \u8b1b\u4e2d\u6587,\u653e\u958b\u81ea\u52d5\u9001\u51fa"}'

daemon_alive=0
if [[ -f "$pid_file" ]]; then
    existing=$(head -n 1 "$pid_file" 2>/dev/null || true)
    if [[ "$existing" =~ ^[0-9]+$ ]] && kill -0 "$existing" 2>/dev/null; then
        daemon_alive=1
    fi
fi

count=0
if [[ $daemon_alive -eq 1 && -f "$sess_file" ]]; then
    count=$(head -n 1 "$sess_file" 2>/dev/null || echo 0)
    [[ "$count" =~ ^[0-9]+$ ]] || count=0
fi
count=$((count + 1))
echo "$count" > "$sess_file"

if [[ $daemon_alive -eq 1 ]]; then
    echo "$msg"
    exit 0
fi

if [[ ! -x "$python_bin" ]]; then
    echo '{"systemMessage":"[kaikou-claude] venv not found. Run install.sh first."}'
    exit 1
fi

# Detach: nohup survives the hook's parent process exiting, redirect stdout
# and stderr to the shared log so print() output is captured.
nohup "$python_bin" "$script" >>"$log_file" 2>&1 &
disown >/dev/null 2>&1 || true

echo "$msg"
exit 0
