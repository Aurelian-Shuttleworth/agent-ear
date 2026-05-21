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
| **How-to** | [Configure GCS Staging](docs/guides/setup-gcs-staging.md) | Large file support (>20MB) |
| **How-to** | [TTS Briefing](docs/guides/tts-briefing.md) | Spoken instructions before recording |
| **How-to** | [Nix Consumer Integration](docs/guides/nix-consumer-integration.md) | Use agent-ear in your flake |
| **Reference** | [CLI Flags](docs/reference/cli.md) | Complete flag reference |
| **Reference** | [Environment Variables](docs/reference/environment-variables.md) | All env vars |
| **Reference** | [Authentication](docs/reference/authentication.md) | Auth resolution & feature matrix |
| **Explanation** | [Architecture](docs/explanation/architecture.md) | Why three binaries? Design decisions |

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

