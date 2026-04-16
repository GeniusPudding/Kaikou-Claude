#!/usr/bin/env bash
# SessionEnd hook: decrement the session counter and kill the daemon only
# when the last session closes. Pass --force (or -Force) to bypass the
# counter — used by uninstall.sh.

set -u

tmp_dir="${TMPDIR:-/tmp}"
pid_file="$tmp_dir/claude-voice.pid"
sess_file="$tmp_dir/claude-voice.sessions"

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
    rm -f "$sess_file"
}

if [[ $force -eq 1 ]]; then
    kill_daemon
    exit 0
fi

count=0
if [[ -f "$sess_file" ]]; then
    count=$(head -n 1 "$sess_file" 2>/dev/null || echo 0)
    [[ "$count" =~ ^[0-9]+$ ]] || count=0
fi
count=$((count - 1))
if (( count <= 0 )); then
    kill_daemon
else
    echo "$count" > "$sess_file"
    echo "session closed; $count session(s) still active; daemon kept alive"
fi
