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
if ((Test-Path $patchScript) -and (Test-Path $settingsFile)) {
    # Try venv Python first, fallback to system Python if venv doesn't exist.
    $pythonCmd = $null
    if (Test-Path $venvPython) {
        $pythonCmd = $venvPython
    } else {
        foreach ($c in @('py', 'python', 'python3')) {
            try {
                $out = & $c --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $pythonCmd = $c
                    break
                }
            } catch {}
        }
    }

    if ($pythonCmd) {
        & $pythonCmd $patchScript $settingsFile uninstall 2>$null
    } else {
        Write-Host 'Python not found; skipping hook removal'
    }
} else {
    Write-Host 'patch_settings.py or settings.json not found; skipping hook removal'
}

# 3. Remove daemon auto-start from PowerShell profile.
$profilePath = $PROFILE.CurrentUserCurrentHost
if ($profilePath -and (Test-Path $profilePath)) {
    $content = Get-Content $profilePath -Raw
    $newContent = $content -replace "# Kaikou-Claude daemon auto-start.*?&`n", ""
    if ($newContent -ne $content) {
        Set-Content -Path $profilePath -Value $newContent
        Write-Host 'Removed daemon auto-start from PowerShell profile'
    }
}

Write-Host ''
Write-Host 'Done. Repo files kept on disk; delete the directory manually to fully remove.'
