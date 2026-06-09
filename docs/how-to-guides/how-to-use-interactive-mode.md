# How to use the Interactive Wizard

This guide shows you how to use the interactive terminal wizard to configure and run agent-ear without memorising CLI flags. 

> [!NOTE] 🔍 **Context for reviewer**
> The wizard is powered by [Gum](https://github.com/charmbracelet/gum) — a CLI tool from Charm that renders interactive prompts, selections, and styled text in the terminal. Think of it as a TUI framework but lighter: no persistent application loop, just composable widgets (choose, input, confirm, file picker) that your shell script calls sequentially.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md)) — Nix recommended
- Authentication configured — either [Google AI Studio](setup-google-ai-studio.md) or [Vertex AI](setup-vertex-ai.md)
- A terminal with a TTY (interactive stdin) — the wizard cannot run inside pipes or headless CI

## When to use interactive mode

AI agents skip the wizard with `--non-interactive` and pass flags directly. Running `agent-ear` **without** the `--non-interactive` flag launches the wizard automatically (provided stdin is a TTY). This is preferable for human users. Here's how to run 'agent-ear' without the '--non-interactive' flag:

```bash
agent-ear
```

## How to interact with the wizard: 

The wizard walks you through four screens in sequence. You can cancel at any point — the script exits cleanly without starting a recording.

### Screen 1 — Mode selection

The wizard asks **"What would you like to do?"** and presents seven modes:

| Mode | Description |
|:-----|:------------|
| 🎤 Record Audio | Freeform voice note — no prompt, just capture and transcribe |
| 🤝 Record Meeting | Multi-speaker conversation with action points and notable quotes |
| 📝 Record Audio (with prompt) | Voice note constrained by a custom system prompt |
| 🗣️ Full Agentic | TTS briefing spoken aloud, then recording with a prompt |
| 🎬 Transcribe Video | Transcribe a local video file |
| 📺 Transcribe YouTube | Transcribe a video from a YouTube URL |
| 📂 Transcribe File | Transcribe an existing audio file (no live recording) |

Use the arrow keys to highlight a mode and press Enter to select it.

> [!TIP] 📸 **Screenshot candidate**
> A screenshot of the Gum mode picker here would help — the styled, emoji-labelled list is much easier to parse visually than a table. Would that be useful?

### Screen 2 — Configuration

After choosing a mode, the wizard prompts for four settings:

1. **Output format** — Choose `markdown`, `json`, or `raw`
2. **Transcription model** — Choose from three tiers:
   - 🟢 Flash-Lite — fast and cheap (default)
   - 🟡 Flash — balanced quality and cost
   - 🔴 Pro — premium, most expensive

   <!-- REVIEW: The model names in the wizard are being updated to match the current defaults. Verify after the fix lands. -->

3. **Output directory** — Defaults to `$AGENT_EAR_OUTPUT_DIR` or the current working directory. Edit inline or accept the default.
4. **Topic slug** — Optional. Leave blank for auto-generation, or type a slug like `sprint-retro-2026-04` to name the output file predictably.

After these four settings, the wizard offers a choice:

- **✅ Continue** — proceed to mode-specific inputs
- **⚙️ Advanced Options** — open the advanced configuration sub-menu (Screen 2b)

### Screen 2b — Advanced options

Most users never need these. Open this sub-menu when you need to:

| Option | What it does | Default |
|:-------|:-------------|:--------|
| Skip prompt validation | Bypass prompt safety checks (`--no-validate`) | Off (validation enabled) |
| High-resolution mode | Send higher-quality frames for text-heavy video (`--high-res`) | Off |
| GCS staging bucket | Override the auto-derived GCS bucket for video staging | Auto-derived from project |
| GCP Project ID | Override `$GOOGLE_CLOUD_PROJECT` / `gcloud config` | Auto-detected |
| Gemini API location | Override the Gemini API regional endpoint | `global` |

### Screen 3 — Mode-specific inputs

Depending on the mode you chose in Screen 1, the wizard collects additional information:

| Mode | What's collected |
|:-----|:-----------------|
| 🎤 Record Audio | *(nothing — straight to confirmation)* |
| 🤝 Record Meeting | Speaker identification method (by name or numbered), participant names if applicable |
| 📝 Record Audio (with prompt) | System prompt — typed inline or selected from a file |
| 🗣️ Full Agentic | System prompt (inline or file) **and** a briefing file (via file picker) |
| 🎬 Transcribe Video | Local video file (via file picker) |
| 📺 Transcribe YouTube | YouTube URL (typed inline) |
| 📂 Transcribe File | Local audio file (via file picker) |

### Screen 4 — Confirmation

The wizard displays a summary of everything you've configured:

```
✅ Ready to go

  Mode:     🎤 Record Audio
  Model:    gemini-3.1-flash-lite-preview
  Format:   markdown
  Output:   /Users/me/notes
  Topic:    [auto-generated]
  Prompt:   [none]
```

Additional lines appear when relevant (Video, Audio file, Briefing, High-res, GCS bucket).

Press Enter on **"Start recording?"** to launch. The wizard hands off to `agent-ear-core --non-interactive` with the assembled flags and **replaces its own process** (`exec`), so you see core's output directly.

## Relationship to CLI flags

The wizard is a convenience layer — it builds the same `agent-ear-core --non-interactive` command you could type yourself. Here's the mapping:

<!-- REVIEW: Does the wizard-to-CLI mapping table make sense? It shows what happens under the hood. -->

| Wizard choice | CLI flag passed to `agent-ear-core` |
|:--------------|:------------------------------------|
| Output format selection | `--output-format <markdown\|json\|raw>` |
| Model tier selection | `--model <model-id>` |
| Output directory | `--output-dir <path>` |
| Topic slug | `--topic <slug>` |
| Inline prompt text | `--prompt "<text>"` |
| Prompt from file | `--prompt-file <path>` |
| Briefing file | `--briefing-file <path>` |
| Video file / YouTube URL | `--video <path-or-url>` |
| Audio input file | `--input-file <path>` |
| High-resolution mode | `--high-res` |
| Skip prompt validation | `--no-validate` |
| GCS staging bucket | `--gcs-bucket <name>` |
| GCP Project ID | `--project-id <id>` |
| Gemini API location | `--location <region>` |
| *(always appended)* | `--non-interactive` |

The `--non-interactive` flag is always appended so that `agent-ear-core` runs non-interactively — the wizard has already collected everything it needs.

> [!TIP] 🎬 **Terminal recording candidate**
> A full walkthrough recording (e.g. with `vhs` or `asciinema`) showing the wizard from mode selection through confirmation would be a valuable companion to this guide. Worth creating?
