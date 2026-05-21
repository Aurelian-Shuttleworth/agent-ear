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
> This is **information-oriented** documentation. It describes the complete CLI interface exhaustively and accurately. For task-oriented usage, see the [[How-to Guides]].

## Synopsis

```
agent-ear [-h] [--prompt-file FILE] [--prompt TEXT]
           [--briefing-file FILE] [--no-validate] [--input-file FILE]
           [--video FILE_OR_URL] [--output-dir DIR]
           [--output-format FMT] [--auto] [--model MODEL]
           [--project-id ID] [--location LOC] [--gcs-bucket BUCKET]
           [--high-res] [--max-tokens N]
```

## Dispatch Behaviour

`agent-ear` is a smart dispatcher. It selects the backend based on context:

| Condition | Backend |
|:----------|:--------|
| `--auto` flag present | `agent-ear-core` (non-interactive pipeline) |
| Non-TTY stdin/stdout | `agent-ear-core` (non-interactive pipeline) |
| Interactive TTY, no `--auto` | `agent-ear-interactive` (Gum TUI wizard) |

Agents **must** always pass `--auto` to bypass the interactive wizard.

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
agent-ear --auto --prompt "Transcribe this standup meeting with action items"

# Prompt from file
agent-ear --auto --prompt-file ./prompts/meeting.md

# With TTS briefing
agent-ear --auto --prompt-file ./prompt.md --briefing-file ./briefing.md

# Skip validation (agent is confident in its prompt)
agent-ear --auto --prompt "Raw capture" --no-validate
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
agent-ear --auto --input-file ./recording.wav

# Transcribe a local video
agent-ear --auto --video ./presentation.mp4

# Transcribe a YouTube video
agent-ear --auto --video "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

---

### Output

Flags that control where and how results are written.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--output-dir DIR` | `path` | Current directory | `AGENT_EAR_OUTPUT_DIR` | Directory to write output files. Created if it does not exist. |
| `--output-format FMT` | `string` | `markdown` | — | Output format. One of: `markdown`, `json`, `raw`. |
| `--auto` | `flag` | `false` | — | Non-interactive mode. Skips the TUI wizard and runs the pipeline directly. **Required for agent-driven usage.** |

#### Output Formats

| Format | Extension | Content |
|:-------|:----------|:--------|
| `markdown` | `.md` | Structured transcript with headers, metadata frontmatter, and formatted sections. |
| `json` | `.json` | Machine-readable JSON with all metadata, token usage, and cost estimate fields. |
| `raw` | `.txt` | Plain text transcript only, no metadata or formatting. |

#### Examples

```bash
# JSON output for programmatic consumption
agent-ear --auto --output-format json --output-dir ./transcripts

# Raw text to stdout-friendly directory
agent-ear --auto --output-format raw --output-dir /tmp/scratch

# Default markdown
agent-ear --auto --output-dir ./notes
```

---

### Model / Project

Flags that configure the Gemini model and Google Cloud project.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--model MODEL` | `string` | `gemini-3.1-flash-lite-preview` | — | Gemini model name for transcription and prompt validation. |
| `--project-id ID` | `string` | Auto-detected | `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID. Enables Vertex AI mode. See [[authentication]]. |
| `--location LOC` | `string` | `global` | `GOOGLE_CLOUD_LOCATION` | Gemini API region. Falls back through: flag → env var → `gcloud config get-value compute/region` → `global`. |
| `--gcs-bucket BUCKET` | `string` | `{project}-transcribe-staging` | `AGENT_EAR_GCS_BUCKET` | GCS bucket name for staging large media files (>20 MB). Auto-provisioned if it does not exist. Requires Vertex AI mode. |

> [!TIP]
> For high-quality meeting transcription, use `--model gemini-3.1-pro-preview`. The default `flash-lite` model is optimised for speed and cost.

#### Examples

```bash
# Use a specific model
agent-ear --auto --model gemini-3.1-pro-preview

# Explicit project and location
agent-ear --auto --project-id my-project --location us-central1

# Custom GCS bucket
agent-ear --auto --gcs-bucket my-custom-bucket --project-id my-project
```

---

### Recording

Flags that control audio/video recording quality and token limits.

| Flag | Type | Default | Env Var | Description |
|:-----|:-----|:--------|:--------|:------------|
| `--high-res` | `flag` | `false` | — | Enable high-resolution audio capture. Increases quality at the cost of larger file size and higher token usage. |
| `--max-tokens N` | `integer` | `8192` (audio) / `16384` (video) | — | Maximum output token count for the Gemini response. Automatically doubled when `--video` is used. |

#### Examples

```bash
# High-res recording for detailed transcription
agent-ear --auto --high-res

# Increase token limit for long meetings
agent-ear --auto --max-tokens 16384

# High-res video with extended token limit
agent-ear --auto --video ./long-meeting.mp4 --high-res --max-tokens 32768
```

---

## Configuration Priority

All settings follow a consistent resolution chain:

```
CLI flag → Environment variable → Auto-detected (gcloud) → Default
```

See [[environment-variables]] for the complete environment variable reference.

## Exit Codes

| Code | Meaning |
|:-----|:--------|
| `0` | Success |
| `1` | Error (auth failure, invalid arguments, runtime error) |
| `2` | Prompt validation failed (prompt scored below quality threshold) |

## See Also

- [[environment-variables]] — Complete environment variable reference
- [[authentication]] — Auth backend selection and troubleshooting
