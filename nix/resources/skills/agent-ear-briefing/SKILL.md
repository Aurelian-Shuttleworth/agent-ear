---
name: agent-ear-briefing
description: >-
  Speak instructions to the user via TTS before recording. Covers briefing
  file format, Director's Notes, voice selection, and validation.
tags: [tts, voice, briefing, agentic]
triggers:
  - "Agent needs to speak to the user"
  - "Workflow needs TTS briefing before recording"
  - "Agent needs to read something aloud"
---

# TTS Briefing

Speak instructions aloud via TTS before starting a recording session.

## Prerequisites

- Auth configured (see `@agent-ear`)
- Audio output available
- A prompt file is REQUIRED (`--briefing-file` requires `--prompt-file`)

## Steps

### 1. Create Briefing File

YAML frontmatter for Director's Notes + markdown body for spoken text:

```markdown
---
voice: Kore
style: warm, conversational
format: inline
---

Hi! I'd like to ask you about your experience with the new feature.
What works well, and what could be improved?
```

**Director's Notes:**

| Field | Values | Default |
|:------|:-------|:--------|
| `voice` | `Kore`, `Aoede`, `Puck`, `Charon`, `Fenrir` | `Kore` |
| `style` | Free-form (e.g., `calm, professional`) | `warm and natural` |
| `format` | `inline` (compact) or `full` (audio profile) | `inline` |

> [!WARNING] Excluded Field: `pace`
> Do NOT use `pace` in Director's Notes. Gemini interprets pace instructions
> too literally, causing syllable-by-syllable speech. This field is intentionally
> stripped by validation.

### 2. Play Briefing

```bash
agent-ear --non-interactive --prompt-file prompt.md --briefing-file briefing.md
```

Flow: TTS plays briefing → user listens → recording starts → user speaks → transcription.

### 3. Validate

Two-layer validation runs automatically:

- **Static checks:** markdown detection, URL detection, length >500 words, pace mismatch
- **LLM judge:** alignment, naturalness, pacing, speakability, length
- Auto-fixes are non-blocking (warns but continues)

## Verification

- TTS audio plays before recording begins
- No validation errors in stderr
- Transcription output matches prompt constraints

## Anti-Patterns

| ❌ Don't | Why |
|:---------|:----|
| Use markdown in briefing text (`**bold**`, `## headers`) | Stripped by validation; confuses TTS |
| Exceed 500 words | TTS timeout and listener fatigue risk |
| Include URLs in briefing | TTS reads character-by-character |
| Use briefing without prompt file | Hard error — `--prompt-file` is required |

## Sharp Edges

| Issue | Severity | Solution |
|:------|:---------|:---------|
| Audio beginning cut off | Low | Pre-warm ping plays 200ms silence first |
| API rate limits on TTS | Medium | Tenacity retries with exponential backoff |
| TTS temperature is 2.0 | Info | Correct for voice generation — not a bug |
