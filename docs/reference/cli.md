---
tags:
  - reference
  - cli
  - agent-ear
creation_date: 2026-05-21
status: active
category: Resource
---

# CLI Reference

> [!NOTE] Diátaxis: Reference
> This is **information-oriented** documentation. It describes the complete CLI interface exhaustively and accurately. For task-oriented usage, see the [How-to Guides](../how-to-guides/).

## Synopsis

```
agent-ear [-h] [--prompt-file FILE] [--prompt TEXT]
           [--briefing-file FILE] [--no-validate] [--input-file FILE]
           [--video FILE_OR_URL] [--output-dir DIR]
           [--output-format FMT] [--non-interactive] [--model MODEL]
           [--project-id ID] [--location LOC] [--gcs-bucket BUCKET]
           [--thinking-level LEVEL] [--high-res] [--max-tokens N]
```

## Dispatch Behaviour

`agent-ear` is a smart dispatcher. It selects the mode based on context:

| Condition | Backend |
|:----------|:--------|
| `--non-interactive` flag present | `agent-ear-core` (non-interactive Python pipeline) |
| Non-TTY stdin/stdout | `agent-ear-core` (non-interactive Python pipeline) |
| Interactive TTY, no `--non-interactive` | Interactive Mode (Gum TUI wizard) |

Agents **must** always pass `--non-interactive` to bypass the interactive wizard.

---

## Flag Reference

### Agentic Inputs

Flags that control the agent's instructions and prompt validation.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--prompt-file FILE` | `path` | — | — | Path to a markdown file containing the transcription prompt. Mutually exclusive with `--prompt`. |
| `--prompt TEXT` | `string` | — | — | Inline transcription prompt text. Mutually exclusive with `--prompt-file`. |
| `--briefing-file FILE` | `path` | — | — | Path to a markdown file containing TTS briefing text. Spoken aloud to the user before recording begins. Supports **Director's Notes** prosody syntax. |
| `--no-validate` | `flag` | `false` | — | Skip LLM-as-a-judge prompt validation. Disables the quality gate that scores prompt clarity and rejects ambiguous instructions. |

#### Examples

```bash
# Inline prompt
agent-ear --non-interactive --prompt "Transcribe this standup meeting with action items"

# Prompt from file
agent-ear --non-interactive --prompt-file ./prompts/meeting.md

# With TTS briefing
agent-ear --non-interactive --prompt-file ./prompt.md --briefing-file ./briefing.md

# Skip validation (agent is confident in its prompt)
agent-ear --non-interactive --prompt "Raw capture" --no-validate
```

---

### Media Inputs

Flags that specify pre-recorded media instead of live microphone capture.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--input-file FILE` | `path` | — | — | Path to a pre-recorded audio file. Skips microphone recording and processes the file directly. |
| `--video FILE_OR_URL` | `string` | — | — | Path to a local video file **or** a YouTube URL. YouTube URLs are downloaded via `yt-dlp` before transcription. |

> [!IMPORTANT]
> When using `--video` with a YouTube URL, `yt-dlp` must be available on `$PATH`. The Nix package includes it automatically.

#### Examples

```bash
# Transcribe a pre-recorded audio file
agent-ear --non-interactive --input-file ./recording.wav

# Transcribe a local video
agent-ear --non-interactive --video ./presentation.mp4

# Transcribe a YouTube video
agent-ear --non-interactive --video "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

---

### Output

Flags that control where and how results are written.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--output-dir DIR` | `path` | Current directory | `AGENT_EAR_OUTPUT_DIR` | Directory to write output files. Created if it does not exist. |
| `--output-format FMT` | `string` | `markdown` | — | Output format. One of: `markdown`, `json`, `raw`. |
| `--non-interactive` | `flag` | `false` | — | Non-interactive mode. Skips the TUI wizard and runs the pipeline directly. **Required for agent-driven usage.** |

#### Output Formats

| Format | Extension | Content |
|:-------|:----------|:--------|
| `markdown` | `.md` | Structured transcript with headers, metadata frontmatter, and formatted sections. |
| `json` | `.json` | Machine-readable JSON with all metadata, token usage, and cost estimate fields. |
| `raw` | `.txt` | Plain text transcript only, no metadata or formatting. |

#### Examples

```bash
# JSON output for programmatic consumption
agent-ear --non-interactive --output-format json --output-dir ./transcripts

# Raw text to stdout-friendly directory
agent-ear --non-interactive --output-format raw --output-dir /tmp/scratch

# Default markdown
agent-ear --non-interactive --output-dir ./notes
```

---

### Model / Project

Flags that configure the Gemini model and Google Cloud project.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--model MODEL` | `string` | `gemini-3.5-flash` | — | Gemini model name for transcription and prompt validation. |
| `--project-id ID` | `string` | Auto-detected | `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID. Enables Vertex AI mode. See [Authentication](authentication.md). |
| `--location LOC` | `string` | `global` | `GOOGLE_CLOUD_LOCATION` | Gemini API region. Falls back through: flag → env var → `gcloud config get-value compute/region` → `global`. |
| `--gcs-bucket BUCKET` | `string` | `{project}-transcribe-staging` | `AGENT_EAR_GCS_BUCKET` | GCS bucket name for staging media files (Vertex AI, or files > 2 GB). Must exist before use. |
| `--thinking-level LEVEL` | `string` | `auto` | `AGENT_EAR_THINKING_LEVEL` | Reasoning depth for transcription: `minimal`, `low`, `medium`, `high`. Auto-resolved from prompt complexity and audio duration if not set. |

> [!TIP]
> The default model is now `gemini-3.5-flash`, which balances quality and speed. For highest quality meeting transcription, use `--model gemini-3.1-pro-preview`.

#### Examples

```bash
# Use a specific model
agent-ear --non-interactive --model gemini-3.1-pro-preview

# Explicit project and location
agent-ear --non-interactive --project-id my-project --location us-central1

# Custom GCS bucket
agent-ear --non-interactive --gcs-bucket my-custom-bucket --project-id my-project

# Control reasoning depth
agent-ear --non-interactive --thinking-level high
```

---

### Recording

Flags that control audio/video recording quality and token limits.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--high-res` | `flag` | `false` | — | Enable high-resolution audio capture. Increases quality at the cost of larger file size and higher token usage. |
| `--max-tokens N` | `integer` | Auto-scaled | — | Maximum output token count for the Gemini response. Auto-scaled (~200 tokens/min of speech, floor 8192, cap 65536). Video defaults to 32768. Overridable. |

#### Examples

```bash
# High-res recording for detailed transcription
agent-ear --non-interactive --high-res

# Increase token limit for long meetings
agent-ear --non-interactive --max-tokens 16384

# High-res video with extended token limit
agent-ear --non-interactive --video ./long-meeting.mp4 --high-res --max-tokens 32768
```

---

## Configuration Priority

All settings follow a consistent resolution chain:

```
CLI flag → Environment variable → Auto-detected (gcloud) → Default
```

See [Environment Variables](environment-variables.md) for the complete environment variable reference.

## Exit Codes

agent-ear uses three exit codes. Agents **must** handle all three to implement robust voice capture workflows.

| Code | Name | Meaning |
|:----:|:-----|:--------|
| `0` | **Success** | Transcription completed. Output file written to `--output-dir`. |
| `1` | **Error** | Unrecoverable failure. |
| `2` | **Prompt Rejected** | Prompt validation failed — the prompt scored below the quality threshold. |

### Exit Code 0 — Success

The transcription pipeline completed successfully. The output file path is printed to stdout (last line). Agents should parse this path to locate the result.

### Exit Code 1 — Error

An unrecoverable error occurred. Common causes:

- **Authentication failure** — No API key or ADC credentials found. See [authentication](authentication.md).
- **Invalid arguments** — Conflicting flags (e.g. `--prompt` and `--prompt-file` together).
- **Network / API error** — Gemini API unreachable, quota exceeded, or model not available.
- **File not found** — `--input-file`, `--video`, `--prompt-file`, or `--briefing-file` path does not exist.
- **Recording failure** — Microphone not available or recording interrupted.

**Agent response:** Log the error, do not retry automatically. Fix the underlying cause.

### Exit Code 2 — Prompt Rejected

The LLM-as-a-Judge prompt validator scored the prompt below the quality threshold. This is a **recoverable** condition — the agent should revise its prompt and retry.

The validator evaluates five criteria:
1. **Specificity** — Does the prompt describe what to extract?
2. **Actionability** — Can the model act on the instructions?
3. **Scope** — Is the task appropriately bounded?
4. **Format guidance** — Does the prompt specify output structure?
5. **Grounding** — Does it reference the audio input?

**Agent response:**
1. Read the validation feedback from stderr.
2. Revise the prompt to address the flagged criteria.
3. Retry with `--prompt "improved prompt text"`.
4. Alternatively, pass `--no-validate` to skip validation (use with caution).

> [!NOTE] Why exit code 2 matters
> Most CLI tools use only 0 (success) and 1 (failure). Exit code 2 means "your input was bad, try again" — it lets agents implement a retry loop where they improve their prompt based on validator feedback, rather than just failing.

```bash
# Example: agent retry loop (pseudocode)
agent-ear --non-interactive --prompt "$PROMPT" 2>validator_feedback.txt
EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
  # Read feedback, revise prompt, retry
  FEEDBACK=$(cat validator_feedback.txt)
  # ... agent revises PROMPT based on FEEDBACK ...
  agent-ear --non-interactive --prompt "$REVISED_PROMPT"
elif [ $EXIT_CODE -eq 1 ]; then
  echo "Fatal error — check logs"
  exit 1
fi
```

## See Also

- [Environment Variables](environment-variables.md) — Complete environment variable reference
- [Authentication](authentication.md) — Auth backend selection and troubleshooting
