# Uninstall kaikou-claude hooks and stop the daemon.
# Repo files are kept on disk; delete manually if no longer needed.

$ErrorActionPreference = 'Continue'
$repoDir       = $PSScriptRoot
$venvPython    = Join-Path $repoDir '.venv\Scripts\python.exe'
$stopScript    = Join-Path $repoDir 'scripts\stop-voice.ps1'
$patchScript   = Join-Path $repoDir 'scripts\patch_settings.py'
$settingsFile  = Join-Path $HOME '.claude\settings.json'

Write-Host ''
Write-Host '=== Kaikou-Claude 解除安裝 ==='

# 1. Stop any live daemon unconditionally (-Force bypasses session counter).
if (Test-Path $stopScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -Force | Out-Null
    Write-Host 'daemon 已停止(若原本在跑)'
}

# 2. Remove our SessionStart/SessionEnd entries from settings.json.
if ((Test-Path $venvPython) -and (Test-Path $patchScript) -and (Test-Path $settingsFile)) {
    & $venvPython $patchScript $settingsFile uninstall
} else {
    Write-Host 'venv 或 settings.json 不在,跳過 hook 清除'
}

Write-Host ''
Write-Host '完成。repo 檔案保留,若要完全移除請自行刪除目錄。'
