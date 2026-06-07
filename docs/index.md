# agent-ear Documentation

<!-- REVIEW: This is the nav root — Docusaurus will use the H1 as the sidebar label unless overridden in sidebars.js -->

> [!NOTE] 🔍 **Context for reviewer**
> This page is organised using the [Diátaxis framework](https://diataxis.fr/) — four quadrants (Tutorials, How-to, Reference, Explanation) that match different user needs. Tutorials teach by doing, How-to guides solve specific problems, Reference is technical facts, and Explanation is the "why" behind design decisions. Does the organisation feel intuitive?

**agent-ear** is an agentic voice capture and transcription CLI. It records audio (or ingests video files and YouTube URLs), transcribes speech using Google's Gemini models with optional constrained prompts, and can speak instructions back to the user via TTS briefings. Designed for AI agent pipelines, it turns spoken input into structured, machine-readable text in a single command.

---

## Quick Links

| Starting point | Go to |
|---|---|
| New to agent-ear? | [Your First Transcription](tutorials/first-transcription.md) — up and recording in 5 minutes |
| Setting up auth? | [Google AI Studio (easy)](guides/setup-google-ai-studio.md) or [Vertex AI (full)](guides/setup-vertex-ai.md) |
| Looking for a flag? | [CLI Reference](reference/cli.md) — every flag, subcommand, and exit code |

---

## Tutorials

*Learning-oriented — follow along step-by-step to build understanding.*

Tutorials walk you through complete workflows from start to finish. They assume no prior experience with agent-ear and focus on getting you to a working result as quickly as possible.

- [Your First Transcription](tutorials/first-transcription.md) — Get recording in 5 minutes

<!-- REVIEW: Should we add a second tutorial for video transcription? It's a distinct enough workflow to warrant its own guide. -->

---

## How-to Guides

*Goal-oriented — solve a specific problem you already understand.*

How-to guides assume you have a working installation and need to accomplish a particular task. Each guide is self-contained and can be read independently.

- [Set up Google AI Studio](guides/setup-google-ai-studio.md) — Free API key authentication
- [Set up Vertex AI](guides/setup-vertex-ai.md) — Full-featured GCP authentication
- [Configure GCS Staging](guides/setup-gcs-staging.md) — GCS staging (Vertex AI / files > 2 GB)
- [TTS Briefing](guides/tts-briefing.md) — Spoken instructions before recording
- [Meeting Transcription](guides/meeting-transcription.md) — Multi-speaker meetings with action items
- [Interactive Mode](guides/interactive-mode.md) — Guided setup via the terminal wizard
- [Nix Consumer Integration](guides/nix-consumer-integration.md) — Use agent-ear in your Nix flake

> [!TIP] 📸 **Screenshot candidate**
> The Interactive Mode guide would benefit from a terminal recording (e.g. asciinema) showing the wizard flow. Worth capturing once the UI is stable.

---

## Reference

*Information-oriented — look up technical facts and specifications.*

Reference material is designed for quick lookup. It is precise, complete, and structured for scanning rather than reading end-to-end.

- [CLI Flags](reference/cli.md) — Complete flag and exit code reference
- [Environment Variables](reference/environment-variables.md) — All configuration env vars
- [Authentication](reference/authentication.md) — Auth resolution order and feature matrix

---

## Explanation

*Understanding-oriented — learn the reasoning behind design decisions.*

Explanation content provides the broader context that other documentation types deliberately leave out. Read these when you want to understand *why* agent-ear works the way it does.

- [Architecture](explanation/architecture.md) — Design decisions, pipeline flow, and cost model
