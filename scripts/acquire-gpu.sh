#!/usr/bin/env bash
# Take the GPU back: remove the sentinel so the daemon reloads its primary
# model onto the GPU. See acquire-gpu.ps1 for full rationale.

set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="${TMPDIR:-/tmp}"
paused_file="$tmp_dir/claude-voice.paused"
pid_file="$tmp_dir/claude-voice.pid"
start_script="$script_dir/start-voice.sh"

if [[ -f "$paused_file" ]]; then
    rm -f "$paused_file"
    echo "Release sentinel removed."
else
    echo "No sentinel present — daemon already in primary mode."
fi

daemon_alive=0
if [[ -f "$pid_file" ]]; then
    existing=$(head -n 1 "$pid_file" 2>/dev/null || true)
    if [[ "$existing" =~ ^[0-9]+$ ]] && kill -0 "$existing" 2>/dev/null; then
        daemon_alive=1
    fi
fi
if [[ $daemon_alive -eq 0 && ( -x "$start_script" || -f "$start_script" ) ]]; then
    echo "Daemon not running -> launching now (model load ~10-15s)."
    bash "$start_script" >/dev/null
else
    echo "Daemon will reload primary onto the GPU within ~1-2s."
fi
