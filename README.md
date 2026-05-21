[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude（開口即克）

Local, offline Chinese voice input for AI coding assistants. Hold a hotkey, speak, release — the transcription is pasted and submitted into the focused window.

Works with **Claude Code** (terminal, VS Code, SSH), **Claude Desktop**, **Gemini Code Assist**, **Aider**, **Codex**, and any other terminal-based AI agent.

Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No API keys. No data leaves your machine.

## Platform support

| Platform | Hotkey | Notes |
|----------|--------|-------|
| Windows  | **Space (hold ≥ 250 ms)** | Tap = literal space, hold = voice. |
| macOS    | **Cmd (hold)** | Instant recording. Cmd+other key = normal shortcut (auto-cancels voice). Requires Accessibility permission. |
| Linux    | F9 (hold) | X11 only. `xdotool` recommended for focus gating. |

> **SSH / remote usage:** Install on the machine where your keyboard is (your local Mac or Windows). The daemon intercepts keys and pastes locally — it works transparently with any terminal connected to a remote host.

## Install

```bash
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude

# Windows
.\install.ps1

# macOS / Linux
./install.sh
```

The installer:

1. Creates `.venv` and installs Python dependencies.
2. Writes a default `.env` (only if missing).
3. Registers `SessionStart` / `SessionEnd` hooks in `~/.claude/settings.json`.
4. Adds a **preexec hook** to your shell config (`~/.bashrc` / `~/.zshrc` / PowerShell `$PROFILE`) so the daemon also auto-starts when you launch other AI agents (Gemini, Aider, etc.) or `ssh`.
5. Pre-downloads the Whisper model (~500 MB `small` on CPU / ~1.6 GB `large-v3-turbo` on CUDA).

Idempotent — re-run any time to upgrade or repair.

## Reinstall / upgrade

```bash
git pull
.\install.ps1        # Windows
./install.sh         # macOS / Linux
```

## Uninstall

```bash
.\uninstall.ps1      # Windows
./uninstall.sh       # macOS / Linux
```

Removes hooks from `~/.claude/settings.json`, removes the preexec block from your shell config, and force-stops the daemon. Repo files stay on disk.

## Usage

After install, just use AI tools as normal — the daemon auto-starts. Hold the hotkey to speak:

| Platform | Action |
|----------|--------|
| Windows | Hold Space ≥ 250 ms → speak → release. Quick taps remain literal spaces. |
| macOS | Hold Cmd → speak → release. Cmd+any key (e.g. Cmd+C) auto-cancels. |
| Linux | Hold F9 → speak → release. |

## How it works

```
                 ┌──────────────────────────────────────────────┐
   Three startup │ Layer 1: Claude SessionStart hook            │
   layers cover  │   → fires when `claude` launches             │
   any AI agent  ├──────────────────────────────────────────────┤
   in any        │ Layer 2: Shell preexec hook                  │
   terminal:     │   → fires on `claude / gemini / aider /      │
                 │     codex / ssh` Enter (zsh preexec, bash    │
                 │     DEBUG trap, PowerShell PSReadLine)       │
                 ├──────────────────────────────────────────────┤
                 │ Layer 3: start-voice self-heal               │
                 │   → recreates venv if missing                │
                 └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ Daemon loaded (Whisper model in memory)      │
              │   → Win32 LL hook (Windows)                  │
              │   → pynput listener (macOS / Linux)          │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ You hold the hotkey                          │
              │   → Focus check: AI agent in foreground?     │
              │       Win32 GetForegroundWindow + tree (Win) │
              │       NSWorkspace + Quartz title (mac)       │
              │       xdotool + tree (Linux)                 │
              │   → Yes: start recording (sounddevice)       │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ You release                                  │
              │   → faster-whisper transcribes locally       │
              │   → Clipboard ← text + <voice> sentinel      │
              │   → Ctrl+V (Cmd+V on mac) into focused win   │
              │   → Enter (if VOICE_AUTO_SUBMIT=1)           │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ All AI sessions closed                       │
              │   → SessionEnd hook checks live processes    │
              │   → Daemon stops only if none remain         │
              │     (incl. SSH sessions, conservative)       │
              └──────────────────────────────────────────────┘
```

Everything runs locally — no network, no API keys, no data leaves your machine.

## Configuration

Edit `.env` in the repo root.

| Variable | Default | Notes |
|----------|---------|-------|
| `VOICE_LANGUAGE` | `zh` | Whisper language hint. |
| `VOICE_AUTO_SUBMIT` | `1` | `0` = paste only, no Enter. Useful for reviewing or mixing voice with typing. |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | Windows Space tap/hold cutoff (not used on macOS). |
| `VOICE_MARKER` | ` <voice>` | Sentinel suffix; empty disables. |
| `WHISPER_MODEL_SIZE` | auto | `large-v3-turbo` on CUDA, `small` on CPU. |
| `WHISPER_DEVICE` | auto | `cuda` or `cpu`. |
| `WHISPER_COMPUTE_TYPE` | auto | `float16` on CUDA, `int8` on CPU. |
| `VOICE_IDLE_UNLOAD_SEC` | `300` | CUDA only: after this many idle seconds, weights are swapped from VRAM to CPU RAM so other workloads can use the GPU. Next transcription pays a ~1-2s reload. Set `0` to keep the model resident on the GPU. |

## Voice marker

Each transcribed prompt is sent as `<text> <voice>`. In Claude Code, `CLAUDE.md` instructs Claude to treat marked prompts as spoken language — tolerate homophones, fix wrong tones, ignore missing punctuation. Other tools receive the raw text plus marker; harmless but you can disable with `VOICE_MARKER=`.

## Logs

| Platform | Log | PID |
|----------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` | `/tmp/claude-voice.pid` |

## Manual daemon control

The daemon usually starts automatically. Manual commands for debugging:

```bash
# Start (idempotent)
.\scripts\start-voice.ps1     # Windows
bash scripts/start-voice.sh   # macOS / Linux

# Force stop
.\scripts\stop-voice.ps1 -Force
bash scripts/stop-voice.sh --force
```

## VS Code notes

Voice works in VS Code's integrated terminal, with two caveats:

1. **Built-in voice conflict** — Claude Code's extension has its own English-only voice on the same hotkey. Install scripts automatically disable it (`voiceEnabled: false`) to avoid garbled output.

2. **Paste target** — VS Code has multiple panels. Ctrl+V goes to whichever panel has cursor focus. **Click the terminal panel before speaking** to ensure the transcription lands in your AI agent rather than a code file.

## Troubleshooting

- **Daemon isn't running.** Check `claude-voice.log`. The daemon auto-starts via `SessionStart` hook (Claude) or preexec hook (other agents / SSH). If it crashed, manually restart with `start-voice.{ps1,sh}`. Persistent failure → re-run install to repair the venv.
- **Hotkey doesn't trigger.** Verify an AI agent process is running (`tasklist` / `ps -ef | grep claude`). Check the log for `● 錄音中...` after you hold the hotkey.
- **macOS: Cmd doesn't work.** Grant Accessibility permission: System Settings → Privacy & Security → Accessibility → add your terminal app.
- **Empty transcription.** Speak for ≥ 0.5s; VAD filters very short clips.
- **Windows: Space stuck.** Force-restart the daemon.

> **Multi-tab terminals** (Windows Terminal, VS Code, Terminal.app, iTerm2) share a single process. Detection applies to the entire app — if one tab has Claude, all tabs in the same window can trigger voice. Acceptable trade-off in practice.
