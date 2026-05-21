---
name: agent-ear
description: >-
  CLI reference for agent-ear — agentic voice capture, constrained transcription,
  and TTS briefing. Covers invocation, auth, exit codes, output formats, models, and costs.
version: 1.1.0
tags: [voice, tts, transcription, multimodal, agentic, cli]
---

# agent-ear — CLI Tool Reference

Agentic voice I/O: TTS briefing → mic recording → constrained transcription. Also ingests local video and YouTube URLs.

## Invocation

```bash
# Installed via Nix (Home Manager or profile)
agent-ear --auto [flags]

# Run without installing
nix run github:Aurelian-Shuttleworth/agent-ear -- --auto [flags]
```

## Authentication

| Backend    | Setup                        | Capabilities                           |
| :--------- | :--------------------------- | :------------------------------------- |
| Vertex AI  | ADC + `GOOGLE_CLOUD_PROJECT` | Full (GCS uploads, all models)         |
| AI Studio  | `GOOGLE_API_KEY` only        | Most features (no GCS, 20 MB limit)    |

Resolution order: `--project-id` → `GOOGLE_CLOUD_PROJECT` → `gcloud config` → API key fallback.

## Exit Codes

| Code | Meaning                              | Agent Action           |
| :--- | :----------------------------------- | :--------------------- |
| 0    | Success                              | Read output file       |
| 1    | Error (recording, transcription, auth) | Report error to user |
| 2    | Prompt validation failed             | Refine prompt and retry |

## Common Operations

| Task             | Command                                                        |
| :--------------- | :------------------------------------------------------------- |
| Record audio     | `agent-ear --auto`                                             |
| Record w/ prompt | `agent-ear --auto --prompt-file prompt.md`                     |
| Transcribe file  | `agent-ear --auto --input-file recording.wav`                  |
| Local video      | `agent-ear --auto --video recording.mp4`                       |
| YouTube          | `agent-ear --auto --video "https://youtube.com/watch?v=..."`   |
| TTS + Record     | `agent-ear --auto --prompt-file p.md --briefing-file b.md`     |
| JSON output      | `agent-ear --auto --output-format json`                        |

## Output Formats

| Format     | Description                                         |
| :--------- | :-------------------------------------------------- |
| `markdown` | YAML frontmatter + structured transcript (default)  |
| `json`     | `{ "date", "slug", "format", "content" }` object    |
| `raw`      | Plain text transcript                                |

## Model Selection

| Model                          | Use Case         | Cost (in / out per 1M tokens) |
| :----------------------------- | :--------------- | :---------------------------- |
| `gemini-3.1-flash-lite-preview` | Audio (default) | $0.30 / $1.50                 |
| `gemini-3-flash-preview`       | Video (default)  | $1.00 / $4.00                 |
| `gemini-3.1-pro-preview`       | Quality          | $1.25 / $10.00                |
| `gemini-2.5-flash-tts`         | TTS briefing     | $0.30 / $2.50                 |

## Sharp Edges

| Issue                                        | Severity   | Mitigation                                |
| :------------------------------------------- | :--------- | :---------------------------------------- |
| Command appears to hang during recording     | **High**   | EXPECTED — do NOT cancel                  |
| `--briefing-file` requires `--prompt-file`   | **Medium** | Always pair briefing with a prompt        |
| Files >20 MB fail in AI Studio mode          | **Medium** | Use Vertex AI for GCS staging             |
| macOS `/tmp` cleanup loses recordings        | **Low**    | Recovery copy saved in `.recovery/`       |
| `pace` field excluded from TTS               | **Low**    | Gemini reads it too literally — omitted   |

## Related Skills

- `@agent-ear-capture` — Recording and transcription workflow
- `@agent-ear-briefing` — TTS briefing creation
- `@agent-ear-video` — Video / YouTube processing
