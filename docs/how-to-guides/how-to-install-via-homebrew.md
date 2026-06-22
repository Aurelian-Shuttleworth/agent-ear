# How to Install agent-ear via Homebrew

Install agent-ear on macOS using Homebrew. This gives you the full tool — interactive wizard, non-interactive agent mode, and all native dependencies — with a single command.

## Prerequisites

- **macOS** (Apple Silicon or Intel)
- **[Homebrew](https://brew.sh)** installed (`brew --version`)

## Install

Add the tap and install:

```bash
brew tap Aurelian-Shuttleworth/tools
brew install agent-ear
```

This installs:

| What | Where | Purpose |
|:-----|:------|:--------|
| `agent-ear` | `$(brew --prefix)/bin/` | Main entry point — interactive TUI wizard |
| `agent-ear-core` | `$(brew --prefix)/bin/` | Python engine — the pipeline that agents and scripts call |
| Prompt templates | `$(brew --prefix)/share/agent-ear-templates/` | Built-in templates for the wizard |

Native dependencies (`gum`, `portaudio`, `libsndfile`, `ffmpeg`, `yt-dlp`) are installed automatically by Homebrew.

## Verify

```bash
# Check both binaries are available
agent-ear --help
agent-ear-core --help

# Launch the interactive wizard (requires a TTY)
agent-ear
```

## Set Up Authentication

agent-ear needs a Google Gemini API connection. The quickest path:

1. Go to [Google AI Studio → API Keys](https://aistudio.google.com/apikey)
2. Click **Create API Key**
3. Export it:

```bash
export GOOGLE_API_KEY="your-key-here"
```

> [!TIP]
> For persistent configuration, add the export to your `~/.zshrc` or `~/.bashrc`. See the [full auth guide](../reference/authentication.md) for Vertex AI and other options.

## Update

```bash
brew upgrade agent-ear
```

## Uninstall

```bash
brew uninstall agent-ear
brew untap Aurelian-Shuttleworth/tools
```

## What's Next?

| Guide | What you'll learn |
|:------|:------------------|
| [Your First Transcription](../tutorials/first-transcription.md) | Full walkthrough of recording and output |
| [Set up Vertex AI](how-to-setup-vertex-ai.md) | Full-featured auth with GCS uploads |
| [Use the Interactive Wizard](how-to-use-interactive-terminal-wizard.md) | Guided setup via the terminal wizard |
| [CLI Reference](../reference/cli.md) | Every flag, exit code, and environment variable |
