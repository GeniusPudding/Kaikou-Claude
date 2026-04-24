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
Write-Host '=== Kaikou-Claude install ==='
Write-Host "Location: $repoDir"

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
    Write-Host 'Python not found. Install Python 3.9+ from python.org first.' -ForegroundColor Red
    exit 1
}

# 2. Version floor — faster-whisper + ctranslate2 wheels require 3.9+.
$pyVerStr = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pyVerStr -lt [version]'3.9') {
    Write-Host "Python $pyVerStr is too old; need 3.9+" -ForegroundColor Red
    exit 1
}

# Note: venv creation and dependency installation are handled by start-voice.ps1
# (it auto-initializes if needed). We only ensure Python exists here.

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
    Write-Host '.env created (auto-detect GPU/CPU)'
}

# 5. Register hooks in user-level settings.json (merge, not replace).
if (-not (Test-Path $settingsDir)) { New-Item -ItemType Directory -Path $settingsDir | Out-Null }

# Need venv for patch_script; ensure it's created first
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoDir 'scripts\start-voice.ps1') 2>$null | Out-Null

$venvPython = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Failed to initialize environment via start-voice.ps1' -ForegroundColor Red
    exit 1
}

& $venvPython $patchScript $settingsFile install win $repoDir
if ($LASTEXITCODE -ne 0) { Write-Host 'Failed to patch settings.json' -ForegroundColor Red; exit 1 }

# 6. Pre-download Whisper model (optional, speeds up first use).
Write-Host 'Downloading Whisper model (cached after first time)...'
& $venvPython -c "
import ctranslate2
from faster_whisper import WhisperModel
device = 'cuda' if ctranslate2.get_cuda_device_count() > 0 else 'cpu'
compute = 'float16' if device == 'cuda' else 'int8'
model_size = 'medium' if device == 'cuda' else 'small'
print(f'  {model_size} ({device}, {compute})')
WhisperModel(model_size, device=device, compute_type=compute)
print('  done')
" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host 'Model download failed (non-fatal; will retry on daemon startup)' -ForegroundColor Yellow }

# 7. If an AI session or SSH connection is already active, start daemon now.
# Whitelist of process names — keep in sync with _AI_TITLE_KEYWORDS in focus.py.
$aliveAgent = @(Get-Process -Name claude -ErrorAction SilentlyContinue) +
              @(Get-Process -Name gemini -ErrorAction SilentlyContinue) +
              @(Get-Process -Name aider -ErrorAction SilentlyContinue) +
              @(Get-Process -Name codex -ErrorAction SilentlyContinue)
$aliveAgent = $aliveAgent | Where-Object { $_ -ne $null }

$sshConnections = @(Get-Process -Name ssh -ErrorAction SilentlyContinue)

if ($aliveAgent.Count -gt 0 -or $sshConnections.Count -gt 0) {
    $msg = "Detected"
    if ($aliveAgent.Count -gt 0) { $msg = "$msg $($aliveAgent.Count) AI session(s)" }
    if ($aliveAgent.Count -gt 0 -and $sshConnections.Count -gt 0) { $msg = "$msg and" }
    if ($sshConnections.Count -gt 0) { $msg = "$msg $($sshConnections.Count) SSH connection(s)" }
    Write-Host "$msg; starting daemon now..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoDir 'scripts\start-voice.ps1') 2>$null | Out-Null
}

# 8. Add daemon auto-start to PowerShell profile (for non-Claude terminals).
$profilePath = $PROFILE.CurrentUserCurrentHost
if ($profilePath) {
    $profileDir = Split-Path -Parent $profilePath
    if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir | Out-Null }

    if (-not (Test-Path $profilePath)) {
        $null > $profilePath
    }

    $profileContent = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
    if ($profileContent -notlike '*Kaikou-Claude daemon auto-start*') {
        "`n# Kaikou-Claude daemon auto-start (any terminal, including SSH)`npowershell -NoProfile -ExecutionPolicy Bypass -File '$repoDir\scripts\start-voice.ps1' 2>$null | Out-Null &`n" | Add-Content -Path $profilePath
        Write-Host "Added daemon auto-start to PowerShell profile"
    }
}

Write-Host ''
Write-Host '=== Done ==='
Write-Host 'Hold Space to speak Chinese -> release to submit'
Write-Host ''
Write-Host 'Uninstall: .\uninstall.ps1'
