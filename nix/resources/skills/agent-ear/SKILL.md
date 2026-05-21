---
name: agent-ear
description: >
  Agentic voice capture, TTS playback, and constrained transcription via
  agent-ear. Supports mic recording, video/YouTube ingestion, and meeting
  mode with action items.
version: 1.1.0
tags: [voice, tts, transcription, multimodal, agentic]
safety_classification: Medium
triggers:
  - "Workflow needs to speak a briefing then capture user response"
  - "User asks to record audio with a specific prompt or structure"
  - "Workflow needs constrained voice transcription (feedback, interview, dictation)"
  - "Agent needs to read something aloud to the user"
  - "User wants to transcribe a video or YouTube URL"
parameters:
  - name: prompt-file
    required: false
    description: System prompt constraining transcription output structure
  - name: briefing-file
    required: false
    description: TTS briefing file spoken to user before recording
  - name: video
    required: false
    description: Video file path or YouTube URL for analysis
requirements: [agent-ear]
---

# agent-ear — Agentic Voice Skill

Unified voice I/O for AI agent workflows. Combines TTS briefing playback, prompted recording, and constrained transcription in a single pipeline.

## Usage

```bash
# Full agentic mode (TTS briefing → record → constrained transcription):
agent-ear --prompt-file prompt.txt --briefing-file brief.md --auto

# TTS-only (speak to user, then record freely):
agent-ear --briefing-file brief.md --auto

# Prompted recording (constrained output, no TTS):
agent-ear --prompt-file prompt.txt --auto

# Standalone recording:
agent-ear --auto

# Video/YouTube analysis:
agent-ear --video recording.mp4 --auto
agent-ear --video "https://youtube.com/watch?v=..." --high-res --auto
```

**Run without installing** (Nix):

```bash
nix run github:Aurelian-Shuttleworth/agent-ear -- --auto
```

## Authentication

agent-ear requires one of:
- `GOOGLE_API_KEY` — Google AI Studio (free, most features, no GCS)
- `GOOGLE_CLOUD_PROJECT` + ADC — Vertex AI (full features incl. GCS staging)

See [Authentication Reference](https://github.com/Aurelian-Shuttleworth/agent-ear/blob/main/docs/reference/authentication.md) for details.

## Creating Briefing Files

Briefing files use YAML frontmatter for director notes + markdown body for spoken text.
The TTS model uses the **Director's Notes + Transcript** format internally —
style goes in `DIRECTOR'S NOTES` (never spoken), text goes in `TRANSCRIPT` (spoken).

```markdown
---
voice: Kore
style: warm, conversational
format: inline
---

Hi! I'd like to ask you about your experience with the new feature.
What works well, and what could be improved?
```

| Field    | Values                                       | Default     |
| :------- | :------------------------------------------- | :---------- |
| `voice`  | `Kore`, `Aoede`, `Puck`, `Charon`, `Fenrir`  | `Kore`      |
| `style`  | Free-form (e.g., `calm, professional`)       | —           |
| `format` | `inline` (compact) or `full` (audio profile) | `inline`    |

## Creating Prompt Files

Prompts constrain transcription output. Write as a plain text system instruction:

```text
You are an expert Product Feedback Analyst extracting structured insights
from recorded interviews.

STRATEGY:
1. Listen to the ENTIRE recording before producing output.
2. Reference specific timestamps (MM:SS) for all key statements or quotes.
3. Prioritise DEPTH over brevity — capture every distinct nuance.

OUTPUT FORMAT — produce a complete Markdown note with ALL sections.

## What Works Well
Comprehensive list of positive feedback.

## Concerns / Suggestions
- **Pain Point**: What the user struggled with (MM:SS)
- **Suggestion**: How they think it could be improved

## Priority Requests
Concrete feature requests or blockers.

## Verbatim Quotes
> "Exact quote" (MM:SS)

DO NOT:
- Produce a brief, shallow summary.
- Skip sections — if a section is sparse, note "None explicitly mentioned".
```

## Pipeline Steps

1. **Prompt validation** — LLM judge checks prompt quality (score 1-5)
2. **Briefing validation** — static + LLM checks for TTS issues, auto-fixes
3. **TTS playback** — speaks briefing (pre-warm ping → audio stream)
4. **Recording** — user records response (press stop / Ctrl+C)
5. **Transcription** — Gemini transcribes with prompt constraints
6. **Cost summary** — prints all API costs (token counts + dollar estimates)

## Exit Criteria

You may exit this skill **only when**:

- Recording completed (user-terminated)
- Transcript returned and saved as markdown
- Cost summary printed

## Anti-Patterns

- ❌ Programmatically sending Ctrl+C or terminating the recording
- ❌ Speaking >500 words in a briefing (TTS timeout risk)
- ❌ Cancelling a command that appears to hang (recording IS the "hang")
- ❌ Putting markdown (`**bold**`, `## headers`) in briefing text

## Sharp Edges

| Issue                                    | Severity   | Solution                                     |
| :--------------------------------------- | :--------- | :------------------------------------------- |
| Command appears to hang during recording | **High**   | EXPECTED — do NOT cancel. User will stop it. |
| Markdown in briefing text                | **Medium** | Auto-detected and stripped by validation     |
| API rate limits on TTS                   | **Medium** | Tenacity retries with exponential backoff    |
| Audio beginning cut off                  | **Low**    | Pre-warm ping plays 200ms silence first      |
| Files >20MB fail in AI Studio mode       | **Medium** | Switch to Vertex AI for GCS staging          |
