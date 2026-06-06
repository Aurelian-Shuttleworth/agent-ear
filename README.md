# agent-ear

**Open-source agentic CLI tool for voice and video comprehension.**

Agent ear offers open-source audio and video comprehension for your agentic IDE, including antigravity. Despite its deep Gemini integration, the tool is CLI-agnostic; it runs wherever command-line execution is available as long as an API key is provided.

**Move Beyond Simplistic Transcription**

Agent-ear's elegant multimodal architecture enables **prosodic contextualization**[^1]: preserving the semantic meaning carried by emphasis, tone, and pacing. By sending media directly to a multimodal model rather than a speech-to-text intermediary, --- . It handles the inherent messiness of unscripted speech from meetings, monologues, YouTube videos, and lecture recordings. WCAG-compatible video descriptions extend this to visual content, ensuring human accessibility for visually impaired users while grounding visual information as machine-readable text that persists for any downstream model.

**End-to-End Agentic Pipeline**

Agent-ear exposes a full pipeline where an AI agent validates its own 'extraction-comprehension prompt', records responses from quick notes to hour-long meetings, transcribes within agent-defined constraints, and can brief human users with spoken instructions using advanced text-to-speech. 

[^1]: prosody - the rhythmic and intonational aspect of language

## Quick Start

### Run without installing (from GitHub)

```bash
nix run github:Aurelian-Shuttleworth/agent-ear
```

### Run locally (from source)

```bash
git clone https://github.com/Aurelian-Shuttleworth/agent-ear.git
cd agent-ear

# Run directly
nix run .

# Or enter the development shell
nix develop
agent-ear
```

## Features

- **🎤 Voice Capture** — Record audio via microphone with automatic silence detection
- **🗣️ TTS Briefing** — Speak instructions to the user before recording (with Director's Notes prosody control)
- **📝 Prompt Validation** — LLM-as-a-judge scoring prevents garbage-in/garbage-out
- **🎬 Video Contextualization** — WCAG-compliant descriptions of local video files or YouTube URLs
- **🤝 Meeting Mode** - Multi-speaker contextualization with action items and notable quotes
- **💰 Cost Tracking** — Per-call token usage and estimated dollar cost reporting
- **📜 Open Source** - Licensed under Apache 2.0.
- **☁️ Smart Upload** — Files up to 2 GB (auto-routed), or GCS staging for larger files

## Architecture

```
agent-ear (Bash wrapper)
├── --auto or non-TTY → exec agent-ear-core (Python pipeline)
└── interactive TTY   → Launch Interactive Mode (Gum TUI wizard)
                             └── exec agent-ear-core --auto
```

Two entry points, one tool:

| Binary | Purpose |
|:-------|:--------|
| `agent-ear` | Main entry point — handles routing and interactive wizard |
| `agent-ear-core` | Python backend — the pipeline that agents and scripts call |

## Usage

### Freeform Recording

```bash
agent-ear --auto --output-format markdown
```

### Meeting Transcription

```bash
agent-ear --auto --prompt "Transcribe this meeting with action items" --model gemini-3.1-pro-preview
```

### Video / YouTube

```bash
agent-ear --auto --video ./presentation.mp4
agent-ear --auto --video "https://youtube.com/watch?v=..."
```

### With TTS Briefing

```bash
agent-ear --auto --prompt-file ./prompt.md --briefing-file ./briefing.md
```

## Configuration

All configuration follows a priority chain:

```
CLI flag → Environment variable → Auto-detected → Default
```

| Setting | CLI Flag | Env Var | Default |
|:--------|:---------|:--------|:--------|
| Output dir | `--output-dir` | `AGENT_EAR_OUTPUT_DIR` | Current directory |
| GCP project | `--project-id` | `GOOGLE_CLOUD_PROJECT` | `gcloud config` |
| GCS bucket | `--gcs-bucket` | `AGENT_EAR_GCS_BUCKET` | `{project}-transcribe-staging` |
| Model | `--model` | — | `gemini-3.1-flash-lite-preview` |

→ Full reference: [CLI flags](docs/reference/cli.md) · [Environment variables](docs/reference/environment-variables.md)

## Authentication

agent-ear supports two authentication backends:

| Backend | Setup | Capabilities |
|:--------|:------|:-------------|
| **Vertex AI** | Application Default Credentials + GCP project | Full (GCS uploads, all models) |
| **Google AI Studio** | `GOOGLE_API_KEY` only | Most features (no GCS) |

→ Setup guides: [Google AI Studio](docs/guides/setup-google-ai-studio.md) · [Vertex AI](docs/guides/setup-vertex-ai.md) · [Auth reference](docs/reference/authentication.md)

## Documentation

Full documentation follows the [Diátaxis](https://diataxis.fr/) framework:

| Type | Document | Description |
|:-----|:---------|:------------|
| **Tutorial** | [Your First Transcription](docs/tutorials/first-transcription.md) | Get recording in 5 minutes |
| **How-to** | [Set up AI Studio](docs/guides/setup-google-ai-studio.md) | Free API key authentication |
| **How-to** | [Set up Vertex AI](docs/guides/setup-vertex-ai.md) | Full-featured GCP authentication |
| **How-to** | [Configure GCS Staging](docs/guides/setup-gcs-staging.md) | GCS staging (Vertex AI / files > 2 GB) |
| **How-to** | [TTS Briefing](docs/guides/tts-briefing.md) | Spoken instructions before recording |
| **How-to** | [Nix Consumer Integration](docs/guides/nix-consumer-integration.md) | Use agent-ear in your flake |
| **Reference** | [CLI Flags](docs/reference/cli.md) | Complete flag reference |
| **Reference** | [Environment Variables](docs/reference/environment-variables.md) | All env vars |
| **Reference** | [Authentication](docs/reference/authentication.md) | Auth resolution & feature matrix |
| **Explanation** | [Architecture](docs/explanation/architecture.md) | Why three entry points? Design decisions |

## For Nix Consumers

### As a flake input

```nix
{
  inputs.agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear";

  # Use the overlay
  nixpkgs.overlays = [ inputs.agent-ear.overlays.default ];

  # Or reference the package directly
  environment.systemPackages = [ inputs.agent-ear.packages.${system}.agent-ear ];
}
```

### As a flake-parts module

```nix
{
  imports = [ inputs.agent-ear.flakeModules.agent-ear ];
  agent-ear.enable = true;
}
```

### With Home Manager (recommended)

Installs the binary, agent skill, and voice-mode workflow automatically:

```nix
{
  # In your flake.nix: apply the overlay
  nixpkgs.overlays = [ inputs.agent-ear.overlays.default ];
}

# In your home-manager config:
{
  imports = [ inputs.agent-ear.homeManagerModules.default ];
  agent-ear.enable = true;
}
```

This places:
- `agent-ear` binary in your PATH
- `~/.gemini/config/skills/agent-ear/SKILL.md` for AI agent auto-discovery
- `~/.gemini/config/workflows/voice-mode.md` for voice interaction workflows

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `agent-ear.enable` | `false` | Enable agent-ear |
| `agent-ear.skills.enable` | `true` | Install skill for AI agent discovery |
| `agent-ear.workflows.enable` | `true` | Install voice-mode workflow |
| `agent-ear.configDir` | `".gemini/config"` | Base path for skills/workflows (change to `".agents"` for Antigravity 2.0) |

→ Full guide: [Nix Consumer Integration](docs/guides/nix-consumer-integration.md)

## Development

```bash
# Enter dev shell
nix develop

# Run checks
nix flake check

# Build the package
nix build
```

## License

Dual-licensed under MIT and Apache 2.0. See [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE).

