# Hand the GPU over to another workload (training, inference, etc.) by
# asking the running voice daemon to switch from CUDA + large-v3-turbo to
# the CPU + small fallback model. Voice keeps working while the GPU is
# released, it's just slower (a few seconds per short utterance).
#
# Pair with acquire-gpu.ps1 to switch back. Both transitions are explicit:
# the daemon never auto-acquires because it has no way to know whether your
# other workload is still using the GPU.
#
# Mechanism: writes a sentinel file (claude-voice.paused). The daemon's
# sentinel watcher thread sees it within ~1 second and calls
# ctranslate2.Whisper.unload_model() on the primary, then lazy-loads the
# CPU fallback. No process is killed; no GPU-wide commands are run.

$pausedFile  = Join-Path $env:TEMP 'claude-voice.paused'
$pidFile     = Join-Path $env:TEMP 'claude-voice.pid'
$startScript = Join-Path $PSScriptRoot 'start-voice.ps1'

Set-Content -Path $pausedFile -Value '' -Encoding ASCII
Write-Host "Release sentinel written: $pausedFile"

# Ensure the daemon is alive so it actually performs the switch. If the
# daemon happens to be dead (crashed, or was killed for an upgrade), launch
# it now — it will read the sentinel at startup and boot directly into
# fallback mode without ever touching the GPU.
$daemonAlive = $false
if (Test-Path $pidFile) {
    $existing = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -match '^\d+$' -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
        $daemonAlive = $true
    }
}
if (-not $daemonAlive -and (Test-Path $startScript)) {
    Write-Host "Daemon not running -> launching (boots straight into fallback mode)."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $startScript | Out-Null
}

Write-Host "Daemon will use CPU fallback model. Voice still works, transcription will be slower."
Write-Host "Resume with: .\scripts\acquire-gpu.ps1"
