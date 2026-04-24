# Daemon Lifecycle Design

## Principle

The daemon should **remain active whenever the user is using any AI agent**, and **automatically stop when all agents are closed**.

**Design Philosophy: Better to stay running than to incorrectly shut down**

## Objectives

The daemon should remain active in these scenarios:

1. **Local Claude Code** - Started via Claude Code SessionStart hook
2. **Local Gemini/Aider/Copilot** - Detected via shell auto-start check
3. **Terminal within IDEs** - VS Code/Cursor/JetBrains integrated terminals
4. **SSH Remote Connections** - User SSHes to a remote machine and opens an agent
5. **RDP/Remote Desktop** - Windows Remote Desktop sessions with agents
6. **Multiple Agent Windows** - User has multiple agent windows open simultaneously

## Architecture

### Three-Layer Startup Protection

```
Layer 1: Claude Code SessionStart Hook
         └─ Triggered when Claude Code session launches
         └─ Calls start-voice.sh / start-voice.ps1

Layer 2: Shell Auto-Start
         └─ Automatically checks on every new terminal
         └─ ~/.bashrc / ~/.zshrc / PowerShell Profile
         └─ Calls start-voice.sh / start-voice.ps1

Layer 3: Intelligent Detection in start-voice.sh/ps1
         └─ Checks if daemon is already running
         └─ Checks if startup is needed (agent processes or terminal windows)
         └─ Starts daemon only if necessary
```

### Shutdown Mechanism

**SessionEnd Hook** - Triggered when Claude Code session closes

```
SessionEnd Decision Logic:
  IF (local agent processes exist) OR (terminal/SSH/IDE windows exist)
    THEN: Keep daemon running
  ELSE: Stop daemon
```

## The Detection Dilemma and Design Trade-off

### The Problem

It is **fundamentally difficult to accurately detect whether an agent is running anywhere on the system**, especially in remote scenarios:

#### Why Precise Detection is Infeasible

1. **Too Many Entry Points**
   - CLI agents launched from various terminal emulators (Terminal.app, iTerm, Warp, etc.)
   - Agents launched from IDE integrated terminals (VS Code, JetBrains, etc.)
   - Agents via SSH remote connections (can't inspect remote process list from local machine)
   - Agents via terminal multiplexers (tmux, screen) - process list doesn't reflect tmux session contents
   - Agents launched in background processes without visible windows

2. **Remote Scenarios are Unobservable**
   ```
   Local machine wants to know:
   - Is there an agent running on remote host X?
   - Is an agent running inside an SSH-forwarded terminal?
   
   But cannot:
   - Connect to every remote host to check processes
   - Know which hosts the user might SSH into
   - Require credentials for remote process inspection
   ```

3. **Process Name Ambiguity**
   ```
   Terminal windows show as "Terminal" or "bash" in process list
   → We can't tell if user is running an agent or just browsing files
   
   SSH connections show as "ssh" process
   → We can't tell if the remote side has an agent running
   ```

4. **Race Conditions**
   ```
   T1: Check processes → No agents found → Decide to stop daemon
   T2: User launches agent
   T3: Daemon is already stopped → Voice feature unavailable ✗
   ```

### Our Solution: Conservative Approach

**Rather than try to perfectly detect all scenarios, we assume conservatively:**

- If ANY terminal-like window is open → daemon might be needed → keep it running
- If ANY SSH connection exists → daemon might be needed on remote side → keep it running
- The cost of incorrectly staying active (minimal CPU) << cost of incorrectly stopping (lost voice feature)

This trades **occasional over-provisioning** for **guaranteed reliability**.

### Trade-offs Explained

| Approach | Pros | Cons |
|----------|------|------|
| **Precise Detection** | Minimal resource usage | Unreliable (misses cases) |
| **Conservative** | Reliable (covers all cases) | Daemon stays running when not needed |

**We chose Conservative** because:
- Daemon uses minimal resources (after model loaded)
- User experience impact of missing voice feature is severe
- False negatives (missing agent) > False positives (daemon stays on)

---

## Platform Implementation

### macOS / Linux (Bash/Zsh)

#### Installation (install.sh)

```bash
1. Verify Python 3.9+
2. Create venv (if needed)
3. Install dependencies
4. Create .env config (if missing)
5. Register Claude SessionStart/End hooks to ~/.claude/settings.json
6. Add auto-start to ~/.bashrc and ~/.zshrc
7. Pre-download Whisper model
8. If active agents detected, start daemon immediately
```

#### Shell Configuration (~/.bashrc / ~/.zshrc)

```bash
# Kaikou-Claude daemon auto-start (any terminal, including SSH)
bash '/path/to/scripts/start-voice.sh' >/dev/null 2>&1 &
```

**When executed**: Automatically on every new terminal session

#### start-voice.sh Logic

```bash
# Step 1: Check if daemon is already running
if daemon_alive; then
    echo "Daemon already running"
    exit 0
fi

# Step 2: Check if venv/dependencies exist
if venv_broken; then
    auto_initialize_venv_and_dependencies()
fi

# Step 3: Start daemon
nohup python voice_to_claude.py >> $log_file 2>&1 &
disown
```

#### stop-voice.sh Logic

```bash
# Check for agent processes
agent_count = count(ps aux | grep -iE 'claude|gemini|aider|codex|copilot')

# Check for terminal/IDE/SSH windows
# (Conservative: assume any of these might contain an agent)
terminal_count = count(ps aux | grep -E 'iTerm|Terminal|Code|ssh|rdesktop')

# Decision
if (agent_count > 0) OR (terminal_count > 0):
    echo "Keeping daemon (agents or terminals still active)"
    exit 0
else:
    kill_daemon()
```

#### Uninstall (uninstall.sh)

```bash
1. Stop daemon (force kill)
2. Remove Claude hooks from ~/.claude/settings.json
3. Remove auto-start from ~/.bashrc / ~/.zshrc
4. Repo files preserved (user deletes manually)
```

### Windows (PowerShell / CMD)

#### Design Direction

Windows should follow the same three-layer protection:

1. **SessionStart Hook** - When Claude Code launches
   - Call start-voice.ps1

2. **Shell Auto-Start** - When new PowerShell/CMD opens
   - PowerShell Profile: `$PROFILE.CurrentUserCurrentHost`
   - CMD: AutoRun registry or launcher wrapper
   - Call start-voice.ps1

3. **start-voice.ps1** - Intelligent check and launch
   - Check if daemon is running
   - Check if startup is needed
   - Launch if necessary

#### stop-voice.ps1 Logic

Check processes:
```powershell
# Agent processes
Get-Process -Name claude,gemini,aider,codex,copilot

# Terminal/IDE/SSH/RDP windows
Get-Process -Name powershell,cmd,ssh,mstsc,putty
```

Decision logic mirrors Linux version.

**Windows-Specific Considerations**:
- PowerShell Execution Policy
- CMD vs PowerShell differences
- OpenSSH on Windows
- RDP (mstsc.exe)
- PuTTY or other SSH clients

---

## Whitelist Keywords

### Agent Process Names

```
claude, gemini, aider, codex, copilot
```

### Terminal/IDE/SSH/RDP Process Names

```
iTerm, Terminal, Terminal.app, Code, ssh, sshpass, rdesktop, 
xfreerdp, mstsc, putty, powershell, cmd, bash, zsh
```

### Regular Expressions

```bash
# Agent processes
grep -iE 'claude|gemini|aider|codex|copilot'

# Terminal/SSH/IDE/RDP
grep -E 'iTerm|Terminal|Code|ssh|rdesktop|mstsc'
```

---

## Logging and Debugging

### Log Locations

| Platform | Log | PID File |
|----------|-----|----------|
| macOS/Linux | `/tmp/claude-voice.log` | `/tmp/claude-voice.pid` |
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |

### Debugging Steps

```bash
# Check if daemon is running
ps aux | grep voice_to_claude

# View recent logs
tail -50 /tmp/claude-voice.log

# Manual daemon start
bash scripts/start-voice.sh

# Manual daemon stop (force)
bash scripts/stop-voice.sh --force

# Check whitelist detection
ps aux | grep -iE 'claude|gemini|aider|codex|copilot'
ps aux | grep -E 'iTerm|Terminal|Code|ssh'
```

---

## Edge Cases

### Case 1: Local terminal open, no local agents, remote SSH with agent

```
Timeline:
T1: User opens local terminal
    → shell auto-start runs start-voice.sh
    → Check: no local agents, but terminal exists → daemon starts ✓

T2: User SSHes to remote and opens Claude
    → Remote session starts
    → Local daemon keeps running (terminal window is active) ✓

T3: User closes SSH and terminal
    → SessionEnd checks: no agents, no terminals
    → daemon stops ✓
```

### Case 2: Multiple Claude windows with IDE terminal

```
Timeline:
T1: Open Claude Code window 1
    → SessionStart hook → daemon starts ✓

T2: Open VS Code with Python terminal
    → shell auto-start → daemon already running ✓

T3: Open Claude Code window 2
    → SessionStart hook → daemon already running ✓

T4: Close window 1
    → SessionEnd check: window 2 exists + IDE terminal active
    → daemon keeps running ✓

T5: Close all windows and terminals
    → SessionEnd check: nothing active
    → daemon stops ✓
```

### Case 3: Broken venv or missing dependencies

```
Flow:
T1: Execute start-voice.sh
T2: Check venv and dependencies
    → If missing → auto-initialize (create venv, install deps)
T3: Start daemon
    → If fails → log error, user can manually run install.sh to repair
```

---

## Verification Checklist

For deployment:

- [ ] SessionStart hook properly registered
- [ ] SessionEnd hook properly registered
- [ ] Shell auto-start config added
- [ ] start-voice.sh detection logic correct
- [ ] stop-voice.sh detection logic correct
- [ ] uninstall.sh fully removes config
- [ ] Daemon auto-starts in all scenarios
- [ ] Daemon auto-stops when all agents closed
- [ ] No false negatives (user can't use voice when agent is running)

---

## Maintenance Guide

### Adding New Agent Support

1. Add new keyword to `focus.py` `_AI_TITLE_KEYWORDS`
2. Add new process name to whitelist in `start-voice.sh` / `stop-voice.sh` / `install.sh`
3. Update whitelist section in this document

### Adding New Terminal/IDE Support

Same as above - add process name to Terminal/IDE whitelist

### Platform-Specific Notes

**macOS**:
- Accessibility permissions may be reset by system updates → daemon needs re-authorization
- `/tmp` directory may be cleaned on system updates
- Braille spinner chars in window title indicate Claude Code

**Linux**:
- WSL vs native Linux may have shell differences
- SSH connections may use different shell (sh vs bash)
- Distribution package managers may have different configurations

**Windows**:
- PowerShell Execution Policy may block script execution
- Ensure OpenSSH service is enabled
- Multiple SSH implementations (OpenSSH, PuTTY) behave differently
- RDP sessions use different process names (mstsc.exe)
