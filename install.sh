#!/usr/bin/env bash
# Install kaikou-claude on macOS / Linux: create venv, install deps,
# register Claude Code hooks. Safe to re-run (idempotent).

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$repo_dir/.venv"
venv_python="$venv_dir/bin/python"
requirements="$repo_dir/requirements.txt"
settings_file="$HOME/.claude/settings.json"
patch_script="$repo_dir/scripts/patch_settings.py"
env_file="$repo_dir/.env"
uname_s="$(uname -s)"

echo
echo "=== Kaikou-Claude 安裝 ==="
echo "位置: $repo_dir"
echo "平台: $uname_s"

# 1. Locate a system Python 3.
python_cmd=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        python_cmd="$candidate"
        break
    fi
done
if [[ -z "$python_cmd" ]]; then
    echo "找不到 Python 3,請先安裝:" >&2
    echo "  macOS: brew install python@3.11" >&2
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv" >&2
    echo "  Fedora: sudo dnf install python3" >&2
    exit 1
fi
echo "Python: $python_cmd ($($python_cmd --version))"

# 2. Enforce >= 3.9.
py_ver=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
py_ver_num=$(echo "$py_ver" | awk -F. '{print $1*100+$2}')
if (( py_ver_num < 309 )); then
    echo "Python $py_ver 太舊,需要 3.9+" >&2
    exit 1
fi

# 3. venv.
if [[ ! -x "$venv_python" ]]; then
    echo "建立 venv..."
    "$python_cmd" -m venv "$venv_dir"
else
    echo "venv 已存在,跳過"
fi

# 4. Dependencies.
echo "安裝依賴(首次會花幾十秒)..."
"$venv_python" -m pip install --upgrade pip >/dev/null
"$venv_python" -m pip install -r "$requirements"

# 5. Linux focus detection falls back to xdotool; warn if missing.
if [[ "$uname_s" == "Linux" ]]; then
    if ! command -v xdotool >/dev/null 2>&1; then
        echo "警告:找不到 xdotool — 焦點偵測將失效(F9 會永遠生效,不限於 CC 焦點)" >&2
        echo "  Ubuntu/Debian: sudo apt install xdotool" >&2
        echo "  Fedora:        sudo dnf install xdotool" >&2
        echo "  Arch:          sudo pacman -S xdotool" >&2
    fi
fi

# 6. Default .env — only if missing.
if [[ ! -f "$env_file" ]]; then
    cat > "$env_file" <<'EOF'
# kaikou-claude runtime config
VOICE_LANGUAGE=zh
VOICE_AUTO_SUBMIT=1
VOICE_MARKER= <voice>

# Model/device auto-detect if left unset:
#   CUDA available -> cuda + medium + float16
#   otherwise       -> cpu  + small  + int8
# Uncomment to force a specific combo:
# WHISPER_MODEL_SIZE=small
# WHISPER_DEVICE=cpu
# WHISPER_COMPUTE_TYPE=int8
EOF
    echo ".env 建立(預設 auto-detect GPU/CPU)"
fi

# 7. Make scripts executable and register hooks.
chmod +x "$repo_dir/scripts/start-voice.sh" "$repo_dir/scripts/stop-voice.sh" 2>/dev/null || true
mkdir -p "$(dirname "$settings_file")"
"$venv_python" "$patch_script" "$settings_file" install unix "$repo_dir"

# 8. Advisory GPU probe.
has_cuda=$("$venv_python" -c "import ctranslate2,sys; sys.stdout.write('1' if ctranslate2.get_cuda_device_count()>0 else '0')" 2>/dev/null || echo 0)
if [[ "$has_cuda" == "1" ]]; then
    device_msg="CUDA 偵測:OK(將使用 GPU + medium 模型)"
else
    device_msg="CUDA 偵測:無(將使用 CPU + small 模型)"
fi

echo
echo "=== 完成 ==="
echo "$device_msg"
echo "打開新的 Claude Code session (\`claude\`) → daemon 自動啟動"
echo "在 Claude Code 視窗按住 F9 講中文 → 放開自動送出"
if [[ "$uname_s" == "Darwin" ]]; then
    echo "(macOS 首次使用會跳 Accessibility 權限請求,同意後才能攔截 F9)"
fi
echo
echo "移除:./uninstall.sh"
