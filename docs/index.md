# agent-ear Documentation

**agent-ear** is an agentic voice capture and transcription CLI. It records audio (or ingests video files and YouTube URLs), transcribes speech using Google's Gemini models with optional constrained prompts, and can speak instructions back to the user via TTS briefings. Designed for AI agent pipelines, it turns spoken input into structured, machine-readable text in a single command.

This documentation is organised using the [Diátaxis framework](https://diataxis.fr/): Tutorials teach by doing, How-to Guides solve specific problems, Explanation covers the "why" behind design decisions, and Reference is technical facts for quick lookup.

---

## Quick Links

| Starting point | Go to |
|---|---|
| New to agent-ear? | [Your First Transcription](tutorials/first-transcription.md) — up and recording in 5 minutes |
| Setting up auth? | [Google AI Studio (easy)](how-to-guides/how-to-setup-google-ai-studio.md) or [Vertex AI (full)](how-to-guides/how-to-setup-vertex-ai.md) |
| Looking for a flag? | [CLI Reference](reference/cli.md) — every flag, subcommand, and exit code |

---

## Tutorials

*Learning-oriented — follow along step-by-step to build understanding.*

Tutorials walk you through complete workflows from start to finish. They assume no prior experience with agent-ear and focus on getting you to a working result as quickly as possible.

- [Your First Transcription](tutorials/first-transcription.md) — Get recording in 5 minutes

---

## How-to Guides

*Goal-oriented — solve a specific problem you already understand.*

How-to guides assume you have a working installation and need to accomplish a particular task. Each guide is self-contained and can be read independently.

- [How to Set Up Google AI Studio Authentication](how-to-guides/how-to-setup-google-ai-studio.md) — Free API key authentication
- [How to Set Up Vertex AI Authentication](how-to-guides/how-to-setup-vertex-ai.md) — Full-featured GCP authentication
- [How to Use the Interactive Wizard](how-to-guides/how-to-use-interactive-mode.md) — Guided setup via the terminal wizard
- [How to Record Meetings with Speaker Labels](how-to-guides/how-to-record-meetings.md) — Multi-speaker meetings with action items
- [How to Write Your Own Prompt Template](how-to-guides/how-to-write-your-own-prompt-template.md) — Custom templates for the wizard
- [How to Set Up GCS Staging](how-to-guides/how-to-setup-gcs-staging.md) — GCS staging (Vertex AI / files > 2 GB)
- [How to Brief Users with Spoken Instructions](how-to-guides/how-to-use-tts-briefing.md) — TTS briefings before recording
- [How to Add agent-ear to Your Nix Flake](how-to-guides/how-to-add-agent-ear-to-nix-flake.md) — Use agent-ear in your Nix flake

---

## Explanation

*Understanding-oriented — learn the reasoning behind design decisions.*

Explanation content provides the broader context that other documentation types deliberately leave out. Read these when you want to understand *why* agent-ear works the way it does.

- [Architecture](explanation/architecture.md) — Design decisions, pipeline flow, and cost model

---

## Reference

*Information-oriented — look up technical facts and specifications.*

Reference material is designed for quick lookup. It is precise, complete, and structured for scanning rather than reading end-to-end.

- [CLI Flags](reference/cli.md) — Complete flag and exit code reference
- [Interactive Wizard Screens](reference/interactive-tui.md) — Screen-by-screen wizard specification
- [Environment Variables](reference/environment-variables.md) — All configuration env vars
- [Authentication](reference/authentication.md) — Auth resolution order and feature matrix
