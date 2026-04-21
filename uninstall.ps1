# Uninstall kaikou-claude hooks and stop the daemon.
# Repo files are kept on disk; delete manually if no longer needed.

$ErrorActionPreference = 'Continue'
$repoDir       = $PSScriptRoot
$venvPython    = Join-Path $repoDir '.venv\Scripts\python.exe'
$stopScript    = Join-Path $repoDir 'scripts\stop-voice.ps1'
$patchScript   = Join-Path $repoDir 'scripts\patch_settings.py'
$settingsFile  = Join-Path $HOME '.claude\settings.json'

Write-Host ''
Write-Host '=== Kaikou-Claude uninstall ==='

# 1. Stop any live daemon unconditionally (-Force bypasses session counter).
if (Test-Path $stopScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -Force | Out-Null
    Write-Host 'Daemon stopped (if it was running)'
}

# 2. Remove our SessionStart/SessionEnd entries from settings.json.
if ((Test-Path $venvPython) -and (Test-Path $patchScript) -and (Test-Path $settingsFile)) {
    & $venvPython $patchScript $settingsFile uninstall
} else {
    Write-Host 'venv or settings.json not found; skipping hook removal'
}

Write-Host ''
Write-Host 'Done. Repo files kept on disk; delete the directory manually to fully remove.'
