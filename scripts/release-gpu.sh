#!/usr/bin/env bash
# Hand the GPU over to another workload by asking the running voice daemon
# to switch from CUDA primary to the CPU fallback model. Voice still works,
# just slower. See release-gpu.ps1 for full rationale.

set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="${TMPDIR:-/tmp}"
paused_file="$tmp_dir/claude-voice.paused"
pid_file="$tmp_dir/claude-voice.pid"
start_script="$script_dir/start-voice.sh"

: > "$paused_file"
echo "Release sentinel written: $paused_file"

daemon_alive=0
if [[ -f "$pid_file" ]]; then
    existing=$(head -n 1 "$pid_file" 2>/dev/null || true)
    if [[ "$existing" =~ ^[0-9]+$ ]] && kill -0 "$existing" 2>/dev/null; then
        daemon_alive=1
    fi
fi
if [[ $daemon_alive -eq 0 && ( -x "$start_script" || -f "$start_script" ) ]]; then
    echo "Daemon not running -> launching (boots straight into fallback mode)."
    bash "$start_script" >/dev/null
fi

echo "Daemon will use CPU fallback model. Voice still works, transcription will be slower."
echo "Resume with: ./scripts/acquire-gpu.sh"
