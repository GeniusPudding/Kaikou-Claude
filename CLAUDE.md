# Project instructions

## Voice input sentinel

Prompts in this project may arrive from a local speech-to-text bridge (`voice_to_claude.py`). Any prompt that ends with the sentinel token ` <voice>` (configurable via `VOICE_MARKER`) was transcribed from the user's speech by faster-whisper, not typed.

When you see this marker:

- Treat the prompt as spoken language. Expect ASR errors: homophones, wrong tones, missing or misplaced punctuation, inserted filler words, and occasional run-on sentences without clear boundaries.
- Infer intent rather than reading the text literally. If a character or word is almost certainly a homophone substitution (e.g. 紀錄 vs 記錄, 的/得/地, 在/再, 做/作), silently use the correct one.
- Do not mention the sentinel or echo it back. Do not ask the user to "re-type" — just proceed with your best interpretation.
- If the transcription is genuinely ambiguous, state the interpretation you are acting on in one short sentence and continue; do not block on a clarifying question for minor ambiguity.
- Strip the sentinel from any quoted copy of the user's prompt before using it in generated code, commit messages, or documentation.

Typed prompts will not carry the marker and should be treated normally.

## Language conventions

- **Code comments, docstrings, and identifier names: English only.** Applies to every source file in this repo (Python, PowerShell, shell, config).
- **README and all Markdown documentation: English only.**
- **User-facing CLI output (print / Write-Host / log banners) is intentionally kept in Traditional Chinese.** This daemon is a Chinese-voice bridge shipped to Chinese-speaking users — the terminal messages they see at startup and during each transcription round are part of the product UX. When adding new `print()` calls that the user will see, write them in Chinese; when adding new `print()` calls that only appear in the debug log, English is fine.
- Conversational replies to the user follow the user's language (Chinese is fine in chat).
- Commit messages: English.

This is a hard rule, not a preference — keep it consistent even when a prompt arrives in Chinese.

## Project layout

- `voice_to_claude.py` — the daemon: Win32 low-level keyboard hook, audio capture, faster-whisper transcription, clipboard-paste-and-submit.
- `start-voice.ps1` / `stop-voice.ps1` — idempotent launcher/stopper, intended to be invoked from a Claude Code SessionStart hook.
- `.env` / `.env.example` — runtime configuration (model size, device, marker token, auto-submit toggle).
- `requirements.txt` — Python dependencies.

The daemon writes its PID to `%TEMP%\claude-voice.pid` and logs to `%TEMP%\claude-voice.log`.
