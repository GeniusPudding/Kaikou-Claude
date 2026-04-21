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
# Whitelist of process names — keep in sync with _AI_TITLE_KEYWORDS in focus.py.
$alive = Get-Process -Name claude,gemini,aider,codex -ErrorAction SilentlyContinue
if ($alive) {
    Write-Host "$($alive.Count) claude process(es) still alive; daemon kept alive"
    exit 0
}

Kill-Daemon
