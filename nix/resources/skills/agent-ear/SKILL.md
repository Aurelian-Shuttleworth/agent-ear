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
agent-ear --non-interactive [flags]

# Run without installing
nix run github:Aurelian-Shuttleworth/agent-ear -- --non-interactive [flags]
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
| Record audio     | `agent-ear --non-interactive`                                             |
| Record w/ prompt | `agent-ear --non-interactive --prompt-file prompt.md`                     |
| Transcribe file  | `agent-ear --non-interactive --input-file recording.wav`                  |
| Local video      | `agent-ear --non-interactive --video recording.mp4`                       |
| YouTube          | `agent-ear --non-interactive --video "https://youtube.com/watch?v=..."`   |
| TTS + Record     | `agent-ear --non-interactive --prompt-file p.md --briefing-file b.md`     |
| JSON output      | `agent-ear --non-interactive --output-format json`                        |

## Token Budget

Output token allocation is automatic — scaled from recording duration (~200 tokens/min, floor 8192, cap 65536). The prompt validator can add up to 16384 extra tokens based on prompt complexity. For known heavy workloads, request more explicitly:

| Flag | Effect |
|:-----|:-------|
| `--extra-tokens N` | Add N tokens to the budget (stacks with validator hint, max +16384). Env: `AGENT_EAR_EXTRA_TOKENS` |
| `--max-tokens N`   | Override the entire budget (ignores duration scaling) |

**When to use `--extra-tokens`:**

| Scenario | Recommended value |
|:---------|:------------------|
| Meeting with 3+ speakers, >30 min | `--extra-tokens 8192` |
| Dense lecture or presentation | `--extra-tokens 4096` |
| Long video (>20 min) | `--extra-tokens 8192` |
| Simple voice note | Not needed (auto-scaling suffices) |

## Output Formats

| Format     | Description                                         |
| :--------- | :-------------------------------------------------- |
| `markdown` | YAML frontmatter + structured transcript (default)  |
| `json`     | `{ "date", "slug", "format", "content" }` object    |
| `raw`      | Plain text transcript                                |

## Model Selection

The default model handles both audio and video. Only override when needed:

| Use case | Flag | When |
|:---------|:-----|:-----|
| Default (audio + video) | _(none — auto-selected)_ | All standard captures |
| Premium quality | `--model gemini-3.1-pro-preview` | Dense multi-speaker content, critical transcriptions |
| TTS briefing | _(auto — not user-selectable)_ | Handled internally |

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
