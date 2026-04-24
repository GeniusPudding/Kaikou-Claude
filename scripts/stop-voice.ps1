# Kill the daemon only when no Claude process remains alive.
# Call with -Force to tear down unconditionally (used by uninstall).

param(
    [switch]$Force
)

$pidFile = Join-Path $env:TEMP 'claude-voice.pid'

function Kill-Daemon {
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p -match '^\d+$') {
            Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
            Write-Host "stopped pid=$p"
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

if ($Force) {
    Kill-Daemon
    exit 0
}

# If any AI agent process is still alive, keep daemon running.
# Also check for SSH/remote sessions in case agent is running on remote machine.
# Whitelist of process names — keep in sync with _AI_TITLE_KEYWORDS in focus.py.
$alive = @(Get-Process -Name claude -ErrorAction SilentlyContinue) +
         @(Get-Process -Name gemini -ErrorAction SilentlyContinue) +
         @(Get-Process -Name aider -ErrorAction SilentlyContinue) +
         @(Get-Process -Name codex -ErrorAction SilentlyContinue)
$alive = $alive | Where-Object { $_ -ne $null }

$sshConnections = @(Get-Process -Name ssh -ErrorAction SilentlyContinue)

if ($alive.Count -gt 0 -or $sshConnections.Count -gt 0) {
    $msg = "daemon kept alive"
    if ($alive.Count -gt 0) { $msg = "$($alive.Count) local AI agent(s) + $msg" }
    if ($sshConnections.Count -gt 0) { $msg = "$msg (+ $($sshConnections.Count) SSH session(s))" }
    Write-Host $msg
    exit 0
}

Kill-Daemon
