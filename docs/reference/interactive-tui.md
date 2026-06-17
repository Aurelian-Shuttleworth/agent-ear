# Interactive Wizard Screens

Screen-by-screen specification of the interactive wizard. This is the canonical reference for the wizard's menus, options, and the CLI flags each choice maps to. For a task-oriented walkthrough, see [How to Use the Interactive Wizard](../how-to-guides/how-to-use-interactive-terminal-wizard.md).

The Wizard is part of the `agent-ear` Shell script and launches automatically when `agent-ear` runs in a TTY without the `--non-interactive` flag. It is built with [Gum](https://github.com/charmbracelet/gum) and assembles a single `agent-ear-core` (Engine) invocation, then replaces its own process (`exec`).

## Screen flow

```
Screen 1: Mode selection
  ├── 🎤 Record Now            → loads Quick Transcript template
  ├── 📝 Custom Prompt         → Screen 3 collects your prompt
  ├── 📋 Templates ▸           → Screen 1b: template picker
  ├── 🎬 Transcribe ▸          → Screen 1c: source picker
  └── ❌ Cancel
Screen 2: Configuration (format, model, output, topic)
Screen 2b: Advanced options (optional)
Screen 3: Mode-specific input (only Custom Prompt and Transcribe modes)
Screen 4: Confirmation (Start / View prompt / Cancel)
```

## Screen 1 — Mode selection

**"What would you like to do?"**

| Choice | Behavior |
|:-------|:---------|
| 🎤 Record Now | Starts immediately with the **Quick Transcript** template — no further mode input |
| 📝 Custom Prompt | Collects your own prompt at Screen 3 (inline or from file) |
| 📋 Templates ▸ | Opens the template picker (Screen 1b) |
| 🎬 Transcribe ▸ | Opens the source picker (Screen 1c) |
| ❌ Cancel | Exits cleanly without recording |

### Screen 1b — Template picker

Lists every template found in `AGENT_EAR_TEMPLATES_DIR` (top level only — `internal/` is hidden). With the packaged templates:

| Template | Purpose |
|:---------|:--------|
| 🎤 Quick Transcript | Clean transcript with key details and action items |
| 🤝 Meeting Notes | Multi-speaker meeting with action items and notable quotes |
| 🧠 Brain Dump | Organise scattered thoughts into categories, actions, and a mind map |
| ✍️ Dictation | Faithful dictation with light cleanup |
| 🎙️ Interview | Q&A-structured interview transcript |
| 🎓 Lecture Notes | Structured study notes from a lecture |
| ↩️ Back | Return to Screen 1 |

Selecting a template loads its prompt body, **skips prompt validation** (curated templates are pre-validated), and merges its frontmatter `tags` into the output's Obsidian frontmatter via `--template-tags`.

### Screen 1c — Transcribe source picker

| Choice | Behavior |
|:-------|:---------|
| 🎬 Transcribe Video — Local file | File picker at Screen 3; applies the internal video template; **enables high-res automatically** |
| 📺 Transcribe YouTube — From URL | URL input at Screen 3; applies the internal YouTube template; **enables high-res automatically** |
| 📂 Transcribe File — Existing audio file | File picker at Screen 3; applies the internal audio template |
| ↩️ Back | Return to Screen 1 |

## Screen 2 — Configuration

1. **Output format** — `markdown` (Obsidian note), `json`, or `raw`
2. **Transcription model** — the wizard fetches live pricing (PriceToken API, 2 s timeout) and shows estimated $/min of transcription next to each model; if the fetch fails it falls back to static labels:

   | Choice | Model ID | Positioning |
   |:-------|:---------|:------------|
   | 🟢 Flash | `gemini-3.5-flash` | fast, balanced (default) |
   | 🟡 Flash-Lite | `gemini-3.1-flash-lite-preview` | cheapest, lower quality |
   | 🔴 Pro | `gemini-3.1-pro-preview` | premium, expensive |

3. **Output directory** — defaults to `$AGENT_EAR_OUTPUT_DIR` or the current working directory
4. **Topic** — optional; leave blank for an auto-generated slug

Then choose **✅ Continue** or **⚙️ Advanced Options**.

## Screen 2b — Advanced options

| Option | CLI equivalent | Default |
|:-------|:---------------|:--------|
| Skip prompt validation | `--no-validate` | Off (validation enabled) |
| High-resolution mode (text-heavy video) | `--high-res` | Off (auto-on for Video/YouTube modes) |
| GCS staging bucket | `--gcs-bucket <name>` | Auto-derived from project |
| GCP Project ID | `--project-id <id>` | `$GOOGLE_CLOUD_PROJECT` / `gcloud config` |
| Gemini API location | `--location <region>` | `global` |

## Screen 3 — Mode-specific input

| Mode | What's collected |
|:-----|:-----------------|
| 🎤 Record Now / 📋 any template | *(nothing — the template already provides the prompt)* |
| 📝 Custom Prompt | Prompt text typed inline, or a prompt file via file picker |
| 🎬 Transcribe Video | Local video file via file picker |
| 📺 Transcribe YouTube | YouTube URL typed inline |
| 📂 Transcribe File | Local audio file via file picker |

## Screen 4 — Confirmation

A summary of every setting, for example:

```
✅ Ready to go

  Mode:     📋 Meeting Notes
  Model:    gemini-3.5-flash
  Format:   markdown
  Output:   /Users/me/notes
  Topic:    [auto-generated]
  Prompt:   🤝 Meeting Notes
```

Additional lines appear when relevant (Video, Audio file, High-res, GCS bucket). Then:

| Choice | Behavior |
|:-------|:---------|
| ✅ Start | `exec`s into `agent-ear-core` with the assembled flags |
| 🔍 View prompt | Opens the full prompt text in a pager, then returns to this screen |
| ❌ Cancel | Exits cleanly |

## Wizard-to-CLI flag mapping

The wizard builds the same command you could type yourself:

| Wizard choice | Flag passed to `agent-ear-core` |
|:--------------|:--------------------------------|
| Output format selection | `--output-format <markdown\|json\|raw>` |
| Model selection | `--model <model-id>` |
| Output directory | `--output-dir <path>` |
| Topic | `--topic <slug>` |
| Template selection / inline prompt | `--prompt "<template or text>"` |
| Prompt from file | `--prompt-file <path>` |
| Template tags | `--template-tags <tag,tag>` |
| Video file / YouTube URL | `--video <path-or-url>` |
| Audio input file | `--input-file <path>` |
| High-resolution mode | `--high-res` |
| Skip prompt validation | `--no-validate` |
| GCS staging bucket | `--gcs-bucket <name>` |
| GCP Project ID | `--project-id <id>` |
| Gemini API location | `--location <region>` |
| *(always appended)* | `--non-interactive` |
