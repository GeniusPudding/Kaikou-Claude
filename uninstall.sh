#!/usr/bin/env bash
# Uninstall kaikou-claude hooks and stop the daemon (macOS / Linux).
# Repo files are kept on disk; delete the directory manually if desired.

set -u

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_python="$repo_dir/.venv/bin/python"
stop_script="$repo_dir/scripts/stop-voice.sh"
patch_script="$repo_dir/scripts/patch_settings.py"
settings_file="$HOME/.claude/settings.json"

echo
echo "=== Kaikou-Claude 解除安裝 ==="

# 1. Force-stop the daemon (safe if none is running).
if [[ -f "$stop_script" ]]; then
    bash "$stop_script" --force >/dev/null 2>&1 || true
    echo "daemon 已停止(若原本在跑)"
fi

# 2. Remove our SessionStart / SessionEnd entries.
if [[ -x "$venv_python" && -f "$patch_script" && -f "$settings_file" ]]; then
    "$venv_python" "$patch_script" "$settings_file" uninstall
else
    echo "venv 或 settings.json 不在,跳過 hook 清除"
fi

echo
echo "完成。repo 檔案保留,若要徹底移除請自行刪除目錄。"
