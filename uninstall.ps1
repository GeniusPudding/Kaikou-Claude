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

# 3. Remove Kaikou-Claude blocks from PowerShell profile (preexec hook + any
# legacy auto-start entries). A block extends from a "Kaikou-Claude" marker
# line to the next blank line or the next line that closes the brace block.
$profilePath = $PROFILE.CurrentUserCurrentHost
if ($profilePath -and (Test-Path $profilePath)) {
    $lines = @(Get-Content $profilePath -ErrorAction SilentlyContinue)
    $kept = New-Object System.Collections.Generic.List[string]
    $skipping = $false
    $braceDepth = 0
    foreach ($line in $lines) {
        if (-not $skipping -and $line -match 'Kaikou-Claude') {
            $skipping = $true
            $braceDepth = 0
        }
        if ($skipping) {
            $braceDepth += ([regex]::Matches($line, '\{')).Count
            $braceDepth -= ([regex]::Matches($line, '\}')).Count
            # End of block: blank line at depth 0, or a line with no braces
            # after we've closed all opened ones.
            if ($braceDepth -le 0 -and ($line.Trim() -eq '' -or $line -match '^\s*\}\s*$')) {
                $skipping = $false
            }
            continue
        }
        $kept.Add($line)
    }
    if ($kept.Count -lt $lines.Count) {
        Set-Content -Path $profilePath -Value $kept
        Write-Host 'Removed Kaikou-Claude block from PowerShell profile'
    }
}

Write-Host ''
Write-Host 'Done. Repo files kept on disk; delete the directory manually to fully remove.'
