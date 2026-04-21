[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude(開口即克)

Local, offline Chinese voice input for [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) and [Claude Desktop](https://claude.ai/download). Hold a hotkey, speak, release — the transcription is pasted and submitted. Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No API keys.

> **Note:** Focus detection matches any window whose process tree contains `claude.exe` or `node … claude`, so both Claude Code (terminal & VS Code extension) and Claude Desktop are supported. The `<voice>` sentinel and ASR error tolerance (via `CLAUDE.md`) are only active in Claude Code; Claude Desktop receives the raw transcription.

## Platform support

| Platform | Status | Hotkey | Notes |
|----------|--------|--------|-------|
| Windows  | **Stable** | **Space (hold)** | Tap = literal space, hold ≥ 250 ms = voice. |
| macOS    | 🚧 Untested | **Cmd (hold alone)** | Cmd+other key = normal shortcut. Requires Accessibility permission. |

> **SSH / remote usage:** Install on the machine where your keyboard is (your local Mac or Windows), not on the remote server. The daemon intercepts keys and pastes locally — it works transparently in SSH terminals running Claude Code on a remote host.
>
> **Linux desktop (rare):** If you're sitting at a physical Linux machine, install locally; the hotkey is F9. Requires X11 and `xdotool`.

## How it works

```
┌─────────────────────────────────────────────────────────┐
│  You open `claude`                                      │
│    → SessionStart hook runs scripts/start-voice.{ps1,sh}│
│    → Daemon launches in background                      │
│    → Whisper model loaded (CUDA auto-detected)          │
│    → Keyboard hook installed                            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  You hold the hotkey (Space on Win, F9 on Mac/Linux)    │
│    → Focus check: foreground process tree has claude?   │
│      • Windows: Win32 GetForegroundWindow + psutil tree │
│      • macOS:   NSWorkspace + psutil tree               │
│      • Linux:   xdotool + psutil tree                   │
│    → If yes: start recording via sounddevice            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  You release the key                                    │
│    → Audio transcribed locally by faster-whisper        │
│    → Text + <voice> marker copied to clipboard          │
│    → Ctrl+V (or Cmd+V on mac) pastes into focused window│
│    → Enter submits (if VOICE_AUTO_SUBMIT=1)             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  You close `claude`                                     │
│    → SessionEnd hook decrements session counter         │
│    → Daemon killed only when counter reaches zero       │
│      (safe for multiple concurrent sessions)            │
└─────────────────────────────────────────────────────────┘
```

Everything runs locally — no network calls, no API keys, no data leaves your machine. The Whisper model is downloaded once from Hugging Face and cached on disk.

## Features

- **Context-aware.** Hotkeys only fire when Claude Code is the foreground process; everywhere else the hook is transparent.
- **Auto paste + submit.** Transcription is pasted via the clipboard and submitted with Enter.
- **Voice sentinel.** Every transcription is suffixed with `<voice>` so Claude knows the prompt came from speech and tolerates ASR errors (see [Voice marker](#voice-marker)).
- **CUDA autodetect.** Falls back to CPU `int8` if no GPU or if model load fails.
- **Multi-session safe.** A session counter keeps the daemon alive while any Claude Code window is open.

## Install

### Windows

```powershell
git clone <repo-url> kaikou-claude
cd kaikou-claude
.\install.ps1
```

### macOS / Linux

```bash
git clone <repo-url> kaikou-claude
cd kaikou-claude
./install.sh
```

The installer creates a local `.venv`, installs dependencies, writes a default `.env` (only if missing), and merges `SessionStart` / `SessionEnd` hooks into `~/.claude/settings.json`. It is idempotent — re-run any time to upgrade or repair.

First `claude` session after install downloads the Whisper weights (~500 MB `small` / ~1.5 GB `medium`).

## Reinstall / upgrade

```powershell
git pull
.\install.ps1        # Windows
./install.sh         # macOS / Linux
```

Same command as first install. Existing `.venv`, `.env`, and hooks are detected and updated in place; previous `kaikou-claude` hook entries are stripped before the new ones are added, so there's no duplication.

## Uninstall

```powershell
.\uninstall.ps1      # Windows
./uninstall.sh       # macOS / Linux
```

Removes this project's `SessionStart` / `SessionEnd` entries from `~/.claude/settings.json` and force-stops the daemon. Other hooks in your settings are preserved. Files on disk (`.venv`, `.env`, source) are kept — delete the directory manually for a clean wipe. To reinstall afterwards, run the install script again.

## Usage

Once installed, just use Claude Code as normal — the daemon auto-starts on each session and shuts down cleanly when the last session ends (see [Multi-session](#multi-session)). The internal launcher scripts under `scripts/` are invoked by the hooks; run them manually only for debugging.

| Key | Action |
|-----|--------|
| Space tap | Literal space (normal typing) |
| Space hold ≥ 250 ms | Record → transcribe → paste → submit |

On macOS, hold Cmd alone (Cmd+other key = normal shortcut, won't trigger voice).

## Configuration

Set in `.env` or the environment.

| Variable | Default | Notes |
|----------|---------|-------|
| `VOICE_LANGUAGE` | `zh` | Whisper language hint |
| `VOICE_AUTO_SUBMIT` | `1` | `0` pastes without pressing Enter — lets you review or mix voice with typed text before submitting manually. With `1` (default), transcription errors are tolerated by Claude via the `<voice>` marker, so auto-submit is safe for most use cases. |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | Space tap/hold cutoff |
| `VOICE_MARKER` | ` <voice>` | Sentinel suffix; empty disables |
| `WHISPER_MODEL_SIZE` | `medium` (cuda) / `small` (cpu) | |
| `WHISPER_DEVICE` | auto | `cuda` or `cpu` |
| `WHISPER_COMPUTE_TYPE` | auto | `float16` / `int8` |

## Voice marker

Each transcribed prompt is sent as:

```
今天天氣如何 <voice>
```

Claude is instructed (via `CLAUDE.md`) to treat marked prompts as spoken language — tolerate homophones, fix wrong tones, ignore missing punctuation, and not echo the tag back. Set `VOICE_MARKER=` to disable.

## Multi-session

The `SessionEnd` hook only kills the daemon when **no `claude` process remains alive** on the system. As long as any Claude Code (or Claude Desktop) window is open, the daemon stays running. `uninstall.{ps1,sh}` and `stop-voice.{ps1,sh} --force` bypass this check and kill unconditionally.

## Logs

| Platform | Log | PID |
|----------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` (or `$TMPDIR`) | `/tmp/claude-voice.pid` |

## Troubleshooting

- **No beep / no action on hotkey.** Focus detection didn't match. Check `claude-voice.log` for a recent `● 錄音中...` line; if absent, the foreground window's process tree doesn't contain a `claude.exe` / `claude` / `node ... claude` process. Verify with `tasklist` (Windows), `ps -ef | grep claude` (Unix).
- **macOS / Linux: nothing happens on F9.** macOS: approve under System Settings → Privacy & Security → Accessibility. Linux: install `xdotool`; Wayland needs XWayland.
- **Empty transcription.** VAD dropped the clip — speak for at least ~500 ms.
- **Windows: Space also types nothing outside Claude Code.** Restart via `scripts\stop-voice.ps1 -Force` then `scripts\start-voice.ps1`.
