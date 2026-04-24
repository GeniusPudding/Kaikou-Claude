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
# Also check for SSH/remote sessions in case agent is running on remote machine.
# Whitelist — keep in sync with _AI_TITLE_KEYWORDS in focus.py.

# Check local agent processes
agent_count=$(ps aux | grep -iE 'claude|gemini|aider|codex' | grep -v grep | grep -v voice_to_claude | wc -l)

# Check for active SSH sessions (user may be connected to remote with agent running)
ssh_count=$(ps aux | grep -E '\bssh\b.*-' | grep -v grep | wc -l)

if (( agent_count > 0 || ssh_count > 0 )); then
    msg="daemon kept alive"
    [[ $agent_count -gt 0 ]] && msg="$agent_count local AI agent(s) + $msg"
    [[ $ssh_count -gt 0 ]] && msg="$msg (+ $ssh_count SSH session(s))"
    echo "$msg"
    exit 0
fi

kill_daemon
