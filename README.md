# agent-ear

**Agentic voice capture, transcription & TTS for AI agents.**

`agent-ear` is a voice pipeline designed to be operated by AI agents. Unlike traditional transcription tools, it exposes a full pipeline where an AI agent validates its own prompt, briefs the human with spoken instructions, records the response, and transcribes it within agent-defined constraints.

## Quick Start

### With Nix (recommended)

```bash
# Run directly from GitHub
nix run github:aurelianshuttleworth/agent-ear

# Or install into your profile
nix profile install github:aurelianshuttleworth/agent-ear
```

### With Docker / Podman

```bash
# Pull and run
docker run --rm -it ghcr.io/aurelianshuttleworth/agent-ear:latest --help
```

## Features

- **🎤 Voice Capture** — Record audio via microphone with automatic silence detection
- **🗣️ TTS Briefing** — Speak instructions to the user before recording (with Director's Notes prosody control)
- **📝 Prompt Validation** — LLM-as-a-judge scoring prevents garbage-in/garbage-out
- **🎬 Video Transcription** — Transcribe local video files or YouTube URLs
- **🤝 Meeting Mode** — Multi-speaker transcription with action items and notable quotes
- **💰 Cost Tracking** — Per-call token usage and estimated dollar cost reporting
- **☁️ GCS Auto-Provisioning** — Automatic staging bucket creation for large files

## Architecture

```
agent-ear (dispatcher)
├── --auto or non-TTY → agent-ear-core (Python pipeline)
└── interactive TTY   → agent-ear-interactive (Gum TUI wizard)
                             └── exec agent-ear-core --auto
```

Three binaries, one tool:

| Binary | Purpose |
|:-------|:--------|
| `agent-ear` | Smart dispatcher — routes based on flags and TTY state |
| `agent-ear-core` | Python backend — the pipeline that agents and scripts call |
| `agent-ear-interactive` | Terminal wizard — guided setup for human users |

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

## Authentication

agent-ear supports two authentication backends:

| Backend | Setup | Capabilities |
|:--------|:------|:-------------|
| **Vertex AI** | Application Default Credentials + GCP project | Full (GCS uploads, all models) |
| **Google AI Studio** | `GOOGLE_API_KEY` only | Most features (no GCS) |

## For Nix Consumers

### As a flake input

```nix
{
  inputs.agent-ear.url = "github:aurelianshuttleworth/agent-ear";

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

## Development

```bash
# Enter dev shell
nix develop

# Run checks
nix flake check

# Build the package
nix build

# Build OCI container
nix build .#container
docker load < result
```

## License

Dual-licensed under MIT and Apache 2.0. See [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE).
