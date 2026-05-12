# Roadmap

Tracks ideas worth exploring next. Not commitments — each item lands only after the design is sound and a test plan exists.

## Voice-invoked skills

Let users trigger Claude Code slash commands by speaking, instead of typing them. Today the daemon pastes the raw transcription; the next step is recognizing skill-invocation intent and rewriting it into `/skill <arg>` form before paste.

**Examples:**

| Spoken (zh) | Rewritten paste |
|-------------|-----------------|
| 切到詳答 / 改成 detailed | `/listen detailed` |
| 換成 brief / 我要簡答 | `/listen brief` |
| 換聲音 換成 zh-CN-XiaoxiaoNeural | `/choose-voice use zh-CN-XiaoxiaoNeural` |
| 列一下 edge 中文聲音 | `/choose-voice list edge Chinese voices` |
| 開啟語音 / 關掉語音 | `/listen on` / `/listen off` |

**Design notes:**

- Skill registry must come from the user's installed skills (`~/.claude/skills/`) — different machines have different sets. Parse each `SKILL.md` frontmatter for `name` + trigger phrases.
- Two-pass match: (1) hard keyword (e.g. 開頭出現 `/listen`), (2) intent classifier on the transcribed text. Pass 1 covers explicit invocations; pass 2 catches natural phrasing.
- Confidence threshold — only rewrite when the match is high-confidence. Below threshold, paste the raw transcript so the user can decide.
- Disambiguation: when two skills match similarly, paste both as candidate prefixes and let user pick.
- Must not fire on dictation that *describes* a skill ("聽我說一下" must not become `/listen`).

**Risks:**

- ASR errors in skill names (Edge / Edge TTS / edge voice 都會被聽錯)
- Over-eager rewriting breaks dictation use-cases
- Different agents (Claude / Gemini / Aider) have different skill systems — initially scope to Claude Code only

**Scope for v1:**

- Whitelist of skill names recognized from the local install
- Only rewrites when transcription *starts* with a trigger keyword
- Configurable on/off via `VOICE_SKILL_MODE` env var (`off` / `strict` / `loose`)

## Other ideas (parking lot)

- Push-to-talk via mouse side button (DPI mouse owners ask for this)
- Per-window hotkey override (Cmd vs Space split for macOS users with mixed terminals)
- Wake-word fallback for hands-busy moments (cooking-while-pairing scenario)
- Whisper.cpp backend option for lower latency on Apple Silicon
- "Undo last paste" hotkey when transcription is wildly wrong

Items here are unsorted and unvetted. Promote to a top-level section before starting work.
