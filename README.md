[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude(開口即克)

Local, offline Chinese voice input for [Claude Code](https://docs.anthropic.com/claude/docs/claude-code). Hold a hotkey in the Claude Code terminal, speak, release — the transcription is pasted and submitted. Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No API keys.

## Platform support

| Platform | Status | Primary hotkey | Backup | Notes |
|----------|--------|----------------|--------|-------|
| Windows  | **Stable** | Space (hold) | F9 (hold) | Win32 LL hook does selective Space suppression — tap = literal space, hold = voice. |
| macOS    | 🚧 Experimental — untested | F9 (hold) | — | Grant Accessibility permission on first run (pynput needs it to observe global keys). |
| Linux    | 🚧 Experimental — untested | F9 (hold) | — | X11 / XWayland only. `xdotool` recommended for focus gating; without it F9 still works but isn't scoped to Claude Code. |

Space is used as a hotkey only on Windows, where the LL hook cleanly distinguishes a tap from a hold. macOS / Linux fall back to F9 because pynput cannot selectively suppress a typing key portably without breaking IME toggles.

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

| Platform | Key | Action |
|----------|-----|--------|
| Windows | Space (tap) | Literal space |
| Windows | Space (hold ≥ 250 ms) | Record → transcribe → paste → submit |
| Windows | F9 (hold) | Same, backup hotkey |
| macOS / Linux | F9 (hold) | Record → transcribe → paste → submit |

Beeps (Windows only): 880 Hz start, 440 Hz stop, 1200 Hz submitted.

## Configuration

Set in `.env` or the environment.

| Variable | Default | Notes |
|----------|---------|-------|
| `VOICE_LANGUAGE` | `zh` | Whisper language hint |
| `VOICE_AUTO_SUBMIT` | `1` | `0` pastes without pressing Enter |
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

A session counter at `%TEMP%\claude-voice.sessions` (`$TMPDIR/claude-voice.sessions` on Unix) is incremented by each `SessionStart` and decremented by each `SessionEnd`. The daemon is only killed when the counter reaches zero — closing one Claude Code window won't break voice in the others. `uninstall.ps1` / `uninstall.sh` and `stop-voice.{ps1,sh} --force` bypass the counter.

## Logs

| Platform | Log | PID |
|----------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` (or `$TMPDIR`) | `/tmp/claude-voice.pid` |

## Troubleshooting

- **No beep / no action on hotkey.** Focus detection didn't match. Check `claude-voice.log` for a recent `● 錄音中...` line; if absent, the foreground window's process tree doesn't contain a `claude.exe` / `claude` / `node ... claude` process. Verify with `tasklist` (Windows), `ps -ef | grep claude` (Unix).
- **macOS: nothing happens on F9.** First run must be approved under System Settings → Privacy & Security → Accessibility. Add your terminal app (or the Python binary) there.
- **Linux: focus gating always False.** Install `xdotool`. Wayland sessions need XWayland; pure Wayland compositors have no portable "active window PID" API.
- **Empty transcription.** VAD dropped the clip — speak for at least ~500 ms.
- **Windows: Space also types nothing outside Claude Code.** Restart via `scripts\stop-voice.ps1 -Force` then `scripts\start-voice.ps1`.
