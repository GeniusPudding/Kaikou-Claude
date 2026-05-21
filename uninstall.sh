#!/usr/bin/env bash
# Uninstall Kaikou-Claude hooks and stop the daemon (macOS / Linux).
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
if [[ -f "$patch_script" && -f "$settings_file" ]]; then
    # Try venv Python first, fallback to system Python if venv doesn't exist.
    python_cmd="$venv_python"
    if [[ ! -x "$python_cmd" ]]; then
        for candidate in python3 python; do
            if command -v "$candidate" >/dev/null 2>&1; then
                python_cmd="$candidate"
                break
            fi
        done
    fi

    if [[ -x "$python_cmd" ]] || command -v "$python_cmd" >/dev/null 2>&1; then
        "$python_cmd" "$patch_script" "$settings_file" uninstall
    else
        echo "Python 找不到,跳過 hook 清除"
    fi
else
    echo "patch_settings.py 或 settings.json 不在,跳過 hook 清除"
fi

# 3. Remove Kaikou-Claude blocks from shell configs (preexec hook + any
# legacy auto-start entries).
for shell_rc in ~/.bashrc ~/.zshrc; do
    if [[ -f "$shell_rc" ]]; then
        # Try GNU sed (-i requires arg), fall back to BSD sed (-i '').
        # The block extends from the marker to the next blank line.
        for marker in 'Kaikou-Claude daemon preexec' 'Kaikou-Claude daemon auto-start'; do
            sed -i.bak "/# $marker/,/^$/d" "$shell_rc" 2>/dev/null || \
            sed -i '' "/# $marker/,/^$/d" "$shell_rc" 2>/dev/null
        done
        rm -f "${shell_rc}.bak" 2>/dev/null
        echo "已從 $shell_rc 移除 Kaikou-Claude 區塊"
    fi
done

echo
echo "完成。repo 檔案保留,若要徹底移除請自行刪除目錄。"
