---
name: agent-ear-video
description: >-
  Transcribe video files and YouTube URLs with agent-ear. Covers local video,
  YouTube download, high-res mode, GCS staging, and Obsidian note integration.
tags: [video, youtube, transcription, multimodal, agentic]
triggers:
  - "User wants to transcribe a video"
  - "Process a YouTube URL into notes"
  - "Agent needs to analyze video content"
---

# agent-ear-video — Video Transcription

Transcribe local video files and YouTube URLs into structured markdown notes
with timestamps, visual descriptions, and optional Obsidian integration.

## Prerequisites

- Auth configured (see `@agent-ear`)
- ffmpeg and yt-dlp bundled (included in Nix package)
- For files >20MB: Vertex AI mode required (GCS staging)

## Steps

### 1. Transcribe Local Video

```bash
agent-ear --non-interactive --video recording.mp4

# High-res mode for text-heavy content (slides, code, whiteboards)
agent-ear --non-interactive --video presentation.mp4 --high-res
```

### 2. Transcribe YouTube

```bash
agent-ear --non-interactive --video "https://youtube.com/watch?v=dQw4w9WgXcQ"

# With custom prompt for structured extraction
agent-ear --non-interactive --video "https://..." --prompt-file extract.md
```

YouTube downloads are capped at 720p — Gemini samples at 1fps, higher is wasted bandwidth.

### 3. Handle Large Files (>20MB)

Requires Vertex AI mode (AI Studio can't do GCS uploads):

```bash
agent-ear --non-interactive --video long_meeting.mp4 --project-id my-project
```

GCS bucket auto-provisioned as `{project}-transcribe-staging` with 7-day lifecycle.
Override: `--gcs-bucket my-bucket` or `AGENT_EAR_GCS_BUCKET` env.

### 4. Integrate with Obsidian

Default output is markdown with YAML frontmatter (`slug`, `tags`, `creation_date`, `status`, `category`).
The default video system prompt includes:

- Timestamps (MM:SS) for all key moments
- Visual descriptions per WCAG SC 1.2.3 accessibility standard
- Executive Summary → Key Points → Detailed Notes structure

Write directly to an Obsidian vault inbox:

```bash
agent-ear --non-interactive --video "https://..." --output-dir /path/to/vault/0.\ Inbox/
```

## Model Selection

| Model                    | When                   | Cost (in / out per 1M) |
| :----------------------- | :--------------------- | :--------------------- |
| `gemini-3-flash-preview` | Default for video      | $1.00 / $4.00         |
| `gemini-3.1-pro-preview` | Dense / complex content | $1.25 / $10.00        |

**Cost awareness:** Video ≈ 25 tokens/second. 10 min video ≈ 15K input tokens ≈ $0.015 (flash).

## Sharp Edges

| Issue                    | Severity | Solution                                       |
| :----------------------- | :------- | :--------------------------------------------- |
| 720p cap                 | Low      | Gemini 1fps sampling — higher res is wasted    |
| >20MB in AI Studio       | Medium   | Switch to Vertex AI for GCS staging            |
| Dynamic token allocation | Info     | >120s audio: ~200 tokens/min auto-scaled, cap 65536 |
