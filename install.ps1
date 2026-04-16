# Install kaikou-claude: create venv, install deps, register Claude Code hooks.
# Safe to re-run (idempotent). Invoke from the repo root: .\install.ps1

$ErrorActionPreference = 'Stop'
$repoDir       = $PSScriptRoot
$venvDir       = Join-Path $repoDir '.venv'
$venvPython    = Join-Path $venvDir 'Scripts\python.exe'
$requirements  = Join-Path $repoDir 'requirements.txt'
$settingsDir   = Join-Path $HOME '.claude'
$settingsFile  = Join-Path $settingsDir 'settings.json'
$patchScript   = Join-Path $repoDir 'scripts\patch_settings.py'
$envFile       = Join-Path $repoDir '.env'

Write-Host ''
Write-Host '=== Kaikou-Claude 安裝 ==='
Write-Host "位置: $repoDir"

# 1. Find a usable system Python (prefer the `py` launcher on Windows).
$pythonCmd = $null
foreach ($c in @('py', 'python', 'python3')) {
    try {
        $out = & $c --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $c
            Write-Host "Python: $c ($out)"
            break
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Host '找不到 Python,請先從 python.org 安裝 3.9+ 再執行此腳本' -ForegroundColor Red
    exit 1
}

# 2. Version floor — faster-whisper + ctranslate2 wheels require 3.9+.
$pyVerStr = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pyVerStr -lt [version]'3.9') {
    Write-Host "Python $pyVerStr 太舊,需要 3.9+" -ForegroundColor Red
    exit 1
}

# 3. venv.
if (-not (Test-Path $venvPython)) {
    Write-Host '建立 venv...'
    & $pythonCmd -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Write-Host 'venv 建立失敗' -ForegroundColor Red; exit 1 }
} else {
    Write-Host 'venv 已存在,跳過'
}

# 4. Dependencies.
Write-Host '安裝依賴(首次會花幾十秒)...'
& $venvPython -m pip install --upgrade pip 2>&1 | Out-Null
& $venvPython -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) { Write-Host '依賴安裝失敗' -ForegroundColor Red; exit 1 }

# 5. .env — only create if missing. Leave device/model unset so the daemon
#    auto-picks CUDA + medium on GPU machines, CPU + small otherwise.
if (-not (Test-Path $envFile)) {
    @(
        '# kaikou-claude runtime config',
        'VOICE_LANGUAGE=zh',
        'VOICE_AUTO_SUBMIT=1',
        'VOICE_MARKER= <voice>',
        '',
        '# Model/device auto-detect if left unset:',
        '#   CUDA available -> cuda + medium + float16',
        '#   otherwise       -> cpu  + small  + int8',
        '# Uncomment to force a specific combo:',
        '# WHISPER_MODEL_SIZE=small',
        '# WHISPER_DEVICE=cpu',
        '# WHISPER_COMPUTE_TYPE=int8'
    ) | Set-Content -Path $envFile -Encoding UTF8
    Write-Host '.env 建立(預設 auto-detect GPU/CPU)'
}

# 6. Register hooks in user-level settings.json (merge, not replace).
if (-not (Test-Path $settingsDir)) { New-Item -ItemType Directory -Path $settingsDir | Out-Null }
& $venvPython $patchScript $settingsFile install win $repoDir
if ($LASTEXITCODE -ne 0) { Write-Host 'settings.json 寫入失敗' -ForegroundColor Red; exit 1 }

# 7. GPU probe — purely informational, does not load the model.
$hasCuda = & $venvPython -c "import ctranslate2,sys; sys.stdout.write('1' if ctranslate2.get_cuda_device_count()>0 else '0')" 2>$null
$deviceMsg = if ($hasCuda -eq '1') { 'CUDA 偵測:✓(將使用 GPU + medium 模型)' } else { 'CUDA 偵測:✗(將使用 CPU + small 模型)' }

Write-Host ''
Write-Host '=== 完成 ==='
Write-Host $deviceMsg
Write-Host '打開新的 Claude Code session(`claude` 指令)→ daemon 自動啟動'
Write-Host '在 Claude Code 輸入框按住空白 ≥0.25 秒講中文 → 放開自動送出'
Write-Host '備用熱鍵:F9'
Write-Host ''
Write-Host '移除:.\uninstall.ps1'
