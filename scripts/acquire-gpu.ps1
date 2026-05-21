# Take the GPU back from the workload that was using it and return the
# voice daemon to its primary model (CUDA + large-v3-turbo).
#
# Mechanism: removes the sentinel file. The daemon's sentinel watcher sees
# it disappear within ~1 second and reloads the primary onto the GPU
# (~1-2s via ctranslate2.Whisper.load_model when the model is already
# instantiated in this process). If the daemon was launched while the
# sentinel was present, primary has never been on the GPU and the load
# is a full from-disk one (~10-15s).

$pausedFile  = Join-Path $env:TEMP 'claude-voice.paused'
$pidFile     = Join-Path $env:TEMP 'claude-voice.pid'
$startScript = Join-Path $PSScriptRoot 'start-voice.ps1'

if (Test-Path $pausedFile) {
    Remove-Item $pausedFile -Force
    Write-Host "Release sentinel removed."
} else {
    Write-Host "No sentinel present — daemon already in primary mode."
}

# Ensure the daemon is alive so it can actually serve voice again.
$daemonAlive = $false
if (Test-Path $pidFile) {
    $existing = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -match '^\d+$' -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
        $daemonAlive = $true
    }
}
if (-not $daemonAlive -and (Test-Path $startScript)) {
    Write-Host "Daemon not running -> launching now (model load ~10-15s)."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $startScript | Out-Null
} else {
    Write-Host "Daemon will reload primary onto the GPU within ~1-2s."
}
