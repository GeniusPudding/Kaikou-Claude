# Idempotent launcher used by Claude Code SessionStart hook.
# If daemon is already alive, does nothing. Otherwise launches it.
# ASCII-only source to avoid cp950 decoding issues under Windows PowerShell 5.x.

$voiceDir = Split-Path -Parent $PSScriptRoot  # this script lives in scripts/
$pidFile  = Join-Path $env:TEMP 'claude-voice.pid'
$pythonw  = Join-Path $voiceDir '.venv\Scripts\pythonw.exe'
$script   = Join-Path $voiceDir 'voice_to_claude.py'

# Hook output: systemMessage shown to user.
$msg = '{"systemMessage":"\u4e2d\u6587\u8a9e\u97f3\u5df2\u555f\u52d5 \u2014 \u6309\u4f4f\u7a7a\u767d\u9375\u8b1b\u4e2d\u6587,\u653e\u958b\u81ea\u52d5\u9001\u51fa(\u77ed\u6309\u7a7a\u767d\u4ecd\u662f\u4e00\u822c\u7a7a\u767d)"}'

# Already running?
if (Test-Path $pidFile) {
    $existing = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -match '^\d+$' -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
        Write-Output $msg
        exit 0
    }
}

if (-not (Test-Path $pythonw)) {
    Write-Error "venv not found; attempting to initialize..." -ErrorAction Continue

    # Try to find system Python
    $python = $null
    foreach ($candidate in @('python', 'python3')) {
        try {
            $version = & $candidate --version 2>$null
            if ($version) {
                $python = $candidate
                break
            }
        } catch {}
    }

    if (-not $python) {
        Write-Output '{"systemMessage":"[kaikou-claude] Python not found. Please install Python 3.9+ or run install.ps1."}'
        exit 1
    }

    # Quick venv setup
    Write-Error "Creating venv..." -ErrorAction Continue
    try {
        & $python -m venv "$voiceDir\.venv" 2>$null
    } catch {
        Write-Output '{"systemMessage":"[kaikou-claude] Failed to create venv. Run install.ps1 to set up properly."}'
        exit 1
    }

    Write-Error "Installing dependencies..." -ErrorAction Continue
    try {
        & $pythonw -m pip install --upgrade pip -q 2>$null
        & $pythonw -m pip install -r "$voiceDir\requirements.txt" -q 2>$null
    } catch {
        Write-Output '{"systemMessage":"[kaikou-claude] Dependency installation failed. Run install.ps1 to fix."}'
        exit 1
    }
}

Start-Process `
    -FilePath $pythonw `
    -ArgumentList "`"$script`"" `
    -WorkingDirectory $voiceDir `
    -WindowStyle Hidden | Out-Null

Write-Output $msg
exit 0
