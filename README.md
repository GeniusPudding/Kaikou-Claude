[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude（開口即克）

Local, offline Chinese voice input for AI coding assistants. Hold a hotkey, speak, release — the transcription is pasted and submitted into the focused window. Works with any terminal-based AI tool: Claude Code, Claude Desktop, Gemini Code Assist, remote agents via SSH, etc.

Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No API keys. No data leaves your machine.

## Supported targets

Voice activates when the foreground window is a recognized terminal (iTerm, Terminal.app, Warp, Windows Terminal) or contains `claude` in its process tree / window title. This covers:

- **Claude Code** — terminal, VS Code integrated terminal, SSH
- **Claude Desktop** — Electron app
- **Gemini Code Assist / other AI agents** — anything running in a terminal window
- **Remote agents via SSH** — daemon runs on your local machine, pastes into the SSH session

## Platform support

| Platform | Status | Hotkey | Notes |
|----------|--------|--------|-------|
| Windows  | **Stable** | **Space (hold)** | Tap = literal space, hold ≥ 250 ms = voice. |
| macOS    | **Stable** | **Cmd (hold)** | Instant recording; Cmd+other key auto-cancels. F9 as backup. Requires Accessibility permission. |

> **SSH / remote usage:** Install on the machine where your keyboard is (your local Mac or Windows), not on the remote server. The daemon intercepts keys and pastes locally — it works transparently with any terminal connected to a remote host.
>
> **Linux desktop (rare):** If sitting at a physical Linux machine, install locally; hotkey is F9. Requires X11 and `xdotool`.

## How it works

```
┌───────────────────────────────────────────────────────────┐
│  You open a Claude Code session (or any supported tool)   │
│    → SessionStart hook launches daemon in background      │
│    → Whisper model loaded (CUDA auto-detected)            │
│    → Keyboard hook installed                              │
└───────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  You hold the hotkey                                      │
│    → Focus check: is foreground a supported target?       │
│      • Windows: Win32 GetForegroundWindow + process tree  │
│      • macOS: NSWorkspace + Quartz window title + tree    │
│      • Linux: xdotool + process tree                      │
│    → If yes: start recording via sounddevice              │
└───────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  You release the key                                      │
│    → Audio transcribed locally by faster-whisper          │
│    → Text copied to clipboard                             │
│    → Ctrl+V (Cmd+V on mac) pastes into focused window    │
│    → Enter submits (if VOICE_AUTO_SUBMIT=1)               │
└───────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  You close all Claude sessions                            │
│    → SessionEnd hook checks for remaining claude processes │
│    → Daemon killed only when none remain                  │
└───────────────────────────────────────────────────────────┘
```

Everything runs locally — no network calls, no API keys, no data leaves your machine.

## Features

- **Context-aware.** Hotkeys only fire when a supported AI tool is the foreground; elsewhere the hook is transparent.
- **Auto paste + submit.** Transcription is pasted via the clipboard and submitted with Enter.
- **Voice sentinel.** Transcriptions are suffixed with `<voice>` so Claude Code knows the prompt came from speech and tolerates ASR errors (see [Voice marker](#voice-marker)).
- **CUDA autodetect.** Falls back to CPU `int8` if no GPU or if model load fails.
- **Daemon lifecycle.** Stays alive as long as any `claude` process exists; auto-killed when all close.

## Install

### Windows

```powershell
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude
./install.sh
```

The installer creates a local `.venv`, installs dependencies, writes a default `.env` (only if missing), and merges `SessionStart` / `SessionEnd` hooks into `~/.claude/settings.json`. It is idempotent — re-run any time to upgrade or repair.

First session after install downloads the Whisper model (~500 MB `small` / ~1.5 GB `medium`).

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

Removes hooks from `~/.claude/settings.json` and force-stops the daemon. Other hooks are preserved. Repo files stay on disk — delete the directory manually for a clean wipe.

## Usage

Once installed, the daemon auto-starts with each Claude Code session. Just hold the hotkey and talk:

| Platform | Key | Action |
|----------|-----|--------|
| Windows | Space tap | Literal space (normal typing) |
| Windows | Space hold ≥ 250 ms | Record → transcribe → paste → submit |
| macOS | Cmd hold | Record instantly → release to submit |
| macOS | Cmd + other key | Normal shortcut (auto-cancels voice) |

## Configuration

Set in `.env` (located in the repo root).

| Variable | Default | Notes |
|----------|---------|-------|
| `VOICE_LANGUAGE` | `zh` | Whisper language hint |
| `VOICE_AUTO_SUBMIT` | `1` | `0` = paste only, don't press Enter. Lets you review/edit or mix voice + typing before submitting. With `1` (default), ASR errors are tolerated via the `<voice>` marker. |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | Windows Space tap/hold cutoff (not used on macOS) |
| `VOICE_MARKER` | ` <voice>` | Sentinel suffix; empty disables |
| `WHISPER_MODEL_SIZE` | auto | `medium` on CUDA, `small` on CPU |
| `WHISPER_DEVICE` | auto | `cuda` or `cpu` |
| `WHISPER_COMPUTE_TYPE` | auto | `float16` on CUDA, `int8` on CPU |

## Voice marker

Each transcribed prompt is sent as:

```
今天天氣如何 <voice>
```

In Claude Code, `CLAUDE.md` instructs Claude to treat `<voice>`-marked prompts as spoken language — tolerate homophones, fix wrong tones, ignore missing punctuation. Other tools (Gemini, Claude Desktop) receive the raw text with the marker; it's harmless but you can disable it with `VOICE_MARKER=`.

## Daemon lifecycle

The daemon stays alive as long as any `claude` process exists on the system. When the last one exits and `SessionEnd` fires, the daemon shuts down. No counter files, no drift — just a live process check.

## Logs

| Platform | Log | PID |
|----------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` | `/tmp/claude-voice.pid` |

## Manually starting / restarting the daemon

If the daemon isn't running (e.g. after an uninstall/reinstall cycle in the same session, or after a crash), start it manually:

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\start-voice.ps1

# macOS / Linux
bash scripts/start-voice.sh
```

To force-restart:

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\stop-voice.ps1 -Force
powershell -ExecutionPolicy Bypass -File scripts\start-voice.ps1

# macOS / Linux
bash scripts/stop-voice.sh --force
bash scripts/start-voice.sh
```

## VS Code notes

Voice works in VS Code's integrated terminal. Two things to know:

1. **Built-in voice conflict.** Claude Code's extension has its own English-only voice on the same hotkey. `install.ps1` / `install.sh` automatically disables it (`voiceEnabled: false`) to avoid garbled output.

2. **Paste target.** VS Code has multiple panels. Ctrl+V goes to whichever panel has cursor focus — if the cursor is in the code editor, the transcription lands there instead of the terminal. **Click the terminal panel before speaking** to ensure correct delivery.

## Troubleshooting

- **Hotkey doesn't trigger.** Check `claude-voice.log` for `● 錄音中...`. If absent, focus detection didn't match. Verify a `claude` process is running (`tasklist` / `ps -ef | grep claude`). Try manually restarting the daemon (see above).
- **macOS: Cmd doesn't work.** Grant Accessibility permission: System Settings → Privacy & Security → Accessibility → add your terminal app.
- **Empty transcription.** Speak for at least ~0.5s; VAD filters very short clips.
- **Windows: Space stuck.** Force-restart the daemon (see above).

> **Note:** Multi-tab terminals (Windows Terminal, VS Code, Terminal.app, iTerm2) share a single process. Voice detection applies to the entire terminal app, not individual tabs — if one tab runs Claude, all tabs in that window can trigger voice. This rarely matters in practice.
