# Decrement the session counter and kill the daemon only when the last session
# closes. Call with -Force to tear the daemon down immediately regardless of
# the counter (used by uninstall.ps1).

param(
    [switch]$Force
)

$pidFile  = Join-Path $env:TEMP 'claude-voice.pid'
$sessFile = Join-Path $env:TEMP 'claude-voice.sessions'

function Kill-Daemon {
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p -match '^\d+$') {
            Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
            Write-Host "stopped pid=$p"
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $sessFile -Force -ErrorAction SilentlyContinue
}

if ($Force) {
    Kill-Daemon
    exit 0
}

# Counter-based: only the last session closing actually kills the daemon.
$count = 0
if (Test-Path $sessFile) {
    $count = [int](Get-Content $sessFile -ErrorAction SilentlyContinue | Select-Object -First 1)
}
$count -= 1
if ($count -le 0) {
    Kill-Daemon
} else {
    $count | Out-File -FilePath $sessFile -Encoding ASCII
    Write-Host "session closed; $count session(s) still active; daemon kept alive"
}
