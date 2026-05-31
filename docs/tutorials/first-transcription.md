# Your First Transcription in 5 Minutes

Welcome! By the end of this page, you'll have recorded your voice (or transcribed a YouTube video) and received a structured Obsidian-ready note — all without installing anything beyond Nix.

## Prerequisites

You need two things:

1. **Nix** — with flakes enabled. If `nix --version` prints something, you're good.
2. **A Google account** — for the Gemini API that powers transcription.

That's it. No Python, no pip, no Docker.

## Choose Your Auth Path

Before we begin, a quick decision:

| | Google AI Studio | Vertex AI |
|:--|:--|:--|
| **Best for** | Trying it out, personal use | Production, enterprise, large files |
| **Setup time** | ~60 seconds | ~5 minutes |
| **Cost** | Free tier available | Pay-as-you-go |
| **Limitations** | Files ≤100 MB inline, ≤2 GB via Files API | Full feature set |

> [!TIP]
> **Just want to try it?** Go with Google AI Studio. You can switch to Vertex AI later — no code changes needed.

If you already have a GCP project with Vertex AI enabled, see the [Vertex AI setup guide](../guides/setup-vertex-ai.md) and skip ahead to [Run your first transcription](#run-your-first-transcription).

## Get a Google AI Studio API Key

1. Open [Google AI Studio → API Keys](https://aistudio.google.com/apikey)
2. Click **Create API Key**
3. Copy the key and export it in your terminal:

```bash
export GOOGLE_API_KEY="your-key-here"
```

> [!NOTE]
> This key stays in your current shell session. For persistence, add the export to your `~/.zshrc` or `~/.bashrc`, or use a secrets manager.

## Run Your First Transcription

One command. Nix fetches everything — Python, audio libraries, the lot.

```bash
nix run github:Aurelian-Shuttleworth/agent-ear -- --auto
```

Here's what happens:

1. 🔑 **Auth** — agent-ear detects your `GOOGLE_API_KEY` and connects to Google AI Studio
2. 🔔 **Ready sound** — a short ping tells you recording has started (macOS)
3. 🎙️ **Recording** — speak naturally. A GUI stop button appears, or press `Ctrl+C`
4. 🛡️ **Safety copy** — your recording is backed up immediately (in case anything goes wrong)
5. 📤 **Upload** — the audio is sent inline to Gemini (files under 100 MB are uploaded inline)
6. ✨ **Transcription** — Gemini produces a structured note with frontmatter, summary, and verbatim transcript
7. 💾 **Saved** — a markdown file lands in your current directory

You'll see output like this:

```
🔑 Auth: Google AI Studio (API key)
🎙️  Recording... Press Ctrl+C to stop.
🛑 Recording stopped.
💾 Saving recording (12.3s)...
🛡️  Recording backed up: ./.recovery/recording_2026-05-21_153012.wav
📤 Inline upload (1.8 MB)
🧠 Using model: gemini-3.5-flash
✨ Generating transcription with gemini-3.5-flash...
✅ Note saved: ./2026-05-21_001_your-topic-slug.md
💰 gemini-3.5-flash: $0.0003 (in: 18,432, out: 512, think: 128)
```

## Try a YouTube Video (No Mic Needed)

Don't have a microphone, or just want to see the output without speaking? Transcribe a YouTube video instead:

```bash
nix run github:Aurelian-Shuttleworth/agent-ear -- --auto --video "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

agent-ear will:

1. ⬇️ Download the video via `yt-dlp` (bundled by Nix — nothing to install)
2. 📤 Upload it to Gemini (inline if under 100 MB, Files API or GCS for larger files)
3. ✨ Produce a timestamped, structured note with executive summary and visual descriptions

> [!NOTE]
> Both audio and video transcription use `gemini-3.5-flash` by default. For highest-quality video analysis, you can specify `--model gemini-3.1-pro-preview`.

## Read the Output

Open the generated `.md` file. Here's what each section does:

```yaml
---
slug: concise-kebab-case-title        # Auto-generated from content
tags:
  - audio-note                        # Or video-note for videos
  - inbox                             # Ready for your Obsidian inbox workflow
creation_date: 2026-05-21
status: inbox
category: To Process
---
```

**`## Executive Summary`** — 3–5 sentences capturing the central thesis. Great for skimming.

**`## Key Points / Action Items`** — Every distinct takeaway as a bullet. Video notes include `MM:SS` timestamps.

**`## Verbatim Transcript`** — For audio: every word exactly as spoken, including filler words (`um`, `uh`). For video: a rich timestamped summary describing both spoken content and on-screen visuals.

The output is designed to drop straight into an [Obsidian](https://obsidian.md) vault, but it's standard markdown — any editor works.

## What's Next?

You've got the basics working. Here's where to go from here:

| Guide | What you'll learn |
|:------|:------------------|
| [Set up Vertex AI](../guides/setup-vertex-ai.md) | Full-featured auth with GCS uploads for large files |
| [Set up GCS staging](../guides/setup-gcs-staging.md) | Cloud storage setup for files over 100 MB |
| [TTS briefing mode](../guides/tts-briefing.md) | Have agent-ear speak instructions before recording |
| [Architecture](../explanation/architecture.md) | Understand why agent-ear is designed the way it is |

> [!TIP]
> If you're using agent-ear from an AI agent (not interactively), always pass `--auto`. This skips interactive prompts and ensures clean JSON-compatible output. See the [CLI reference](../reference/cli.md) for the full flag list.
