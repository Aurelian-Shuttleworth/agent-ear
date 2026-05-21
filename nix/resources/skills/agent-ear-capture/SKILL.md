---
name: agent-ear-capture
description: >-
  Record and transcribe audio with agent-ear. Covers prompt authoring,
  constrained transcription, and output verification.
tags: [voice, transcription, recording, agentic]
triggers:
  - "User needs to record and transcribe audio"
  - "Workflow needs constrained voice transcription"
  - "Agent needs to capture user's spoken response"
---

# Audio Capture & Transcription

Record user speech and produce structured transcription via `agent-ear`.

## Prerequisites

- Auth configured (see `@agent-ear`)
- Microphone available (or use `--input-file` for existing audio)

## Steps

### 1. Prepare Prompt (Optional)

Create a prompt file to constrain transcription output. An LLM judge scores it on 5 criteria:

| # | Criterion | What to include |
|:--|:----------|:----------------|
| 1 | Instruction clarity | Specific extraction targets |
| 2 | Output structure | Defined format (markdown sections, YAML) |
| 3 | Grounding | Timestamp requirement (`MM:SS`) |
| 4 | Negative constraints | Explicit `DO NOT` guidelines |
| 5 | Completeness | Edge cases (silence, background noise) |

```text
Transcribe this recording as structured feedback.

## What Works Well
- Positive feedback with timestamps (MM:SS)

## Concerns
- Pain points with timestamps

DO NOT: produce a brief summary. Be thorough.
```

### 2. Record

```bash
# Freeform (no prompt)
agent-ear --auto

# Constrained by prompt
agent-ear --auto --prompt-file prompt.md

# From existing file (skip recording)
agent-ear --auto --input-file recording.wav
```

> [!WARNING] Recording Behavior
> The command appears to hang during recording — this is EXPECTED.
> Do NOT cancel. The user will press Stop or Ctrl+C when finished.

### 3. Verify Output

1. Check exit code: `0` = success, `2` = refine prompt and retry
2. Read the output file (markdown with YAML frontmatter by default)
3. If interrupted, check `.recovery/recording_*.wav` in the output dir

## Verification

- Output file exists and contains YAML frontmatter
- Content matches prompt constraints (sections, timestamps)
- Exit code is `0`

## Anti-Patterns

| ❌ Don't | Why |
|:---------|:----|
| Programmatically cancel the recording | Kills the user's session mid-speech |
| Skip prompt for structured capture tasks | Output will be unstructured freeform |
| Use `--model gemini-3.1-pro-preview` for simple notes | Unnecessary cost; default model suffices |
