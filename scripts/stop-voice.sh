#!/usr/bin/env bash
# Kill the daemon only when no Claude process remains alive.
# Pass --force to tear down unconditionally (used by uninstall.sh).

set -u

tmp_dir="${TMPDIR:-/tmp}"
pid_file="$tmp_dir/claude-voice.pid"

force=0
case "${1:-}" in
    --force|-Force|-f) force=1 ;;
esac

kill_daemon() {
    if [[ -f "$pid_file" ]]; then
        p=$(head -n 1 "$pid_file" 2>/dev/null || true)
        if [[ "$p" =~ ^[0-9]+$ ]]; then
            kill -TERM "$p" 2>/dev/null || true
            sleep 0.2
            kill -KILL "$p" 2>/dev/null || true
            echo "stopped pid=$p"
        fi
        rm -f "$pid_file"
    fi
}

if [[ $force -eq 1 ]]; then
    kill_daemon
    exit 0
fi

# If any AI agent process is still alive, keep daemon running.
# Whitelist — keep in sync with _AI_TITLE_KEYWORDS in focus.py.
agent_count=$(pgrep -c -f 'claude|gemini|aider|codex' 2>/dev/null || echo 0)
if (( agent_count > 0 )); then
    echo "$agent_count AI agent process(es) still alive; daemon kept alive"
    exit 0
fi

kill_daemon
