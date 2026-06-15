# How to Use the Interactive Wizard

This guide shows you how to use the interactive terminal wizard to configure and run agent-ear without memorising CLI flags. For the complete list of every screen, menu option, and flag mapping, see the [Interactive Wizard Screens reference](../reference/interactive-tui.md).

## Prerequisites

- `agent-ear` installed (see [README](../../README.md)) — Nix recommended
- Authentication configured — either [Google AI Studio](how-to-setup-google-ai-studio.md) or [Vertex AI](how-to-setup-vertex-ai.md)
- A terminal with a TTY (interactive stdin) — the wizard cannot run inside pipes or headless CI

## When to use the Wizard

AI agents skip the Wizard with `--non-interactive` and pass flags directly. Running `agent-ear` **without** that flag launches the Wizard automatically (provided stdin is a TTY) — this is the preferred path for human users:

```bash
agent-ear
```

## Walkthrough: record a quick voice note

1. **Pick a mode.** The wizard opens with **"What would you like to do?"**. For the fastest path, choose **🎤 Record Now** — it uses the built-in Quick Transcript template, so you skip prompt-writing entirely. Prefer a purpose-built prompt? Choose **📋 Templates ▸** and pick one (Meeting Notes, Brain Dump, Dictation, Interview, Lecture Notes), or **📝 Custom Prompt** to write your own.

2. **Configure the basics.** The wizard asks for output format (`markdown` for Obsidian notes), transcription model (live $/min pricing is shown next to each — 🟢 Flash is the default), output directory, and an optional topic for the filename. Most users accept the defaults; **⚙️ Advanced Options** (GCS bucket, high-res video, validation skip) is there if you need it.

3. **Provide mode-specific input.** Only some modes ask for more: Custom Prompt collects your prompt (inline or from a file); the Transcribe modes collect a video file, YouTube URL, or audio file. Record Now and template modes go straight to confirmation.

4. **Confirm and record.** Review the summary screen. Choose **🔍 View prompt** to read the exact prompt that will steer the transcription, then **✅ Start**. The wizard hands off to `agent-ear-core` and you see the pipeline's output directly: recording starts, and pressing the stop control ends it and begins transcription.

Your note lands in the output directory as `{date}_{seq}_{slug}.md`, ready for Obsidian.

## Tips

- **Templates skip validation.** Curated templates are pre-validated, so template runs start faster than custom prompts (which pass through the LLM-as-a-judge check first).
- **Video and YouTube modes enable high-res automatically** for faithful transcription of slides and on-screen text.
- **You can cancel at any screen** — the wizard exits cleanly without recording.
- **Everything the wizard does maps to CLI flags.** Once a flow feels repetitive, lift the equivalent flags from the [mapping table](../reference/interactive-tui.md#wizard-to-cli-flag-mapping) and script it.
