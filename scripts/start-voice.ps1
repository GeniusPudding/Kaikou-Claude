# Idempotent launcher used by Claude Code SessionStart hook.
# Portable: resolves everything relative to this script's directory.
# ASCII-only source to avoid cp950 decoding issues under Windows PowerShell 5.x.

$voiceDir    = Split-Path -Parent $PSScriptRoot  # this script lives in scripts/
$pidFile     = Join-Path $env:TEMP 'claude-voice.pid'
$sessFile    = Join-Path $env:TEMP 'claude-voice.sessions'
$pythonw     = Join-Path $voiceDir '.venv\Scripts\pythonw.exe'
$script      = Join-Path $voiceDir 'voice_to_claude.py'

# Hook output: systemMessage shown to user. ASCII-safe JSON with unicode escapes.
$msg = '{"systemMessage":"\u4e2d\u6587\u8a9e\u97f3\u5df2\u555f\u52d5 \u2014 \u6309\u4f4f\u7a7a\u767d\u9375\u8b1b\u4e2d\u6587,\u653e\u958b\u81ea\u52d5\u9001\u51fa(\u77ed\u6309\u7a7a\u767d\u4ecd\u662f\u4e00\u822c\u7a7a\u767d)"}'

# Reference counter so concurrent sessions share one daemon (see stop-voice.ps1).
# Reset counter if the previous daemon is dead (crash recovery).
$daemonAlive = $false
if (Test-Path $pidFile) {
    $existing = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -match '^\d+$' -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
        $daemonAlive = $true
    }
}

$count = 0
if ($daemonAlive -and (Test-Path $sessFile)) {
    $count = [int](Get-Content $sessFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($count -lt 0) { $count = 0 }
}
$count += 1
$count | Out-File -FilePath $sessFile -Encoding ASCII

if ($daemonAlive) {
    Write-Output $msg
    exit 0
}

if (-not (Test-Path $pythonw)) {
    Write-Output '{"systemMessage":"[kaikou-claude] venv not found. Run install.ps1 first."}'
    exit 1
}

Start-Process `
    -FilePath $pythonw `
    -ArgumentList "`"$script`"" `
    -WorkingDirectory $voiceDir `
    -WindowStyle Hidden | Out-Null

Write-Output $msg
exit 0
