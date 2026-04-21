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

# If any claude process is still alive, keep daemon running.
claude_count=$(pgrep -c -f '[c]laude' 2>/dev/null || echo 0)
if (( claude_count > 0 )); then
    echo "$claude_count claude process(es) still alive; daemon kept alive"
    exit 0
fi

kill_daemon
