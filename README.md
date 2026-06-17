# agent-ear

[![CI](https://github.com/Aurelian-Shuttleworth/agent-ear/actions/workflows/ci.yml/badge.svg)](https://github.com/Aurelian-Shuttleworth/agent-ear/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT%20%26%20Apache--2.0-blue.svg)](LICENSE-MIT)
[![Nix](https://img.shields.io/badge/built%20with-Nix-7e7eff.svg)](https://nixos.org/)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/Aurelian-Shuttleworth/agent-ear/badge)](https://securityscorecards.dev/viewer/?uri=github.com/Aurelian-Shuttleworth/agent-ear)

**Open-source agentic CLI tool for voice and video comprehension.**

> [!WARNING]
> **Alpha Release:** agent-ear is in active development. APIs and configuration flags may change before v1.0 stable.

Agent ear offers open-source audio and video comprehension for your agentic IDE, including Antigravity. Despite its deep Gemini integration, the tool is CLI-agnostic; it runs wherever command-line execution is available as long as an API key is provided.

**Move Beyond Simplistic Transcription**

Agent-ear's elegant multimodal architecture enables **prosodic contextualization**[^1]: preserving the semantic meaning carried by emphasis, tone, and pacing. By sending media directly to a multimodal model rather than a speech-to-text intermediary, the model hears what plain transcription throws away — the stress, hesitation, and timing that change what words actually mean. It handles the inherent messiness of unscripted speech from meetings, monologues, YouTube videos, and lecture recordings. WCAG-compatible video descriptions extend this to visual content, ensuring human accessibility for visually impaired users while grounding visual information as machine-readable text that persists for any downstream model.

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

- **🎤 Voice Capture** — Record audio via microphone; stop with `Ctrl+C` or the on-screen button
- **🗣️ TTS Briefing** — Speak instructions to the user before recording (with Director's Notes prosody control)
- **📝 Prompt Validation** — LLM-as-a-judge scoring prevents garbage-in/garbage-out
- **🎬 Video Contextualization** — WCAG-compliant descriptions of local video files or YouTube URLs
- **🤝 Meeting Mode** - Multi-speaker contextualization with action items and notable quotes
- **💰 Cost Tracking** — Per-call token usage and estimated dollar cost reporting
- **📜 Open Source** - Licensed under Apache 2.0.
- **☁️ Smart Upload** — Files up to 2 GB (auto-routed), or GCS staging for larger files

## Architecture

```
agent-ear (the Shell)
├── --non-interactive or non-TTY → exec agent-ear-core (the Engine)
└── interactive TTY   → Launch the Wizard (interactive TUI)
                             └── exec agent-ear-core --non-interactive
```

Two entry points, one tool:

| Binary | Purpose |
|:-------|:--------|
| `agent-ear` | Main entry point (the **Shell**) — handles routing and the Wizard |
| `agent-ear-core` | The **Engine** — the Pipeline that agents and scripts call |

## Usage

### Freeform Recording

```bash
agent-ear --non-interactive --output-format markdown
```

### Meeting Transcription

```bash
agent-ear --non-interactive --prompt "Transcribe this meeting with action items" --model gemini-3.1-pro-preview
```

### Video / YouTube

```bash
agent-ear --non-interactive --video ./presentation.mp4
agent-ear --non-interactive --video "https://youtube.com/watch?v=..."
```

### With TTS Briefing

```bash
agent-ear --non-interactive --prompt-file ./prompt.md --briefing-file ./briefing.md
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
| Model | `--model` | — | `gemini-3.5-flash` |

→ Full reference: [CLI flags](docs/reference/cli.md) · [Environment variables](docs/reference/environment-variables.md)

## Authentication

agent-ear supports two authentication backends:

| Backend | Setup | Capabilities |
|:--------|:------|:-------------|
| **Vertex AI** | Application Default Credentials + GCP project | Full (GCS uploads, all models) |
| **Google AI Studio** | `GOOGLE_API_KEY` only | Most features (no GCS) |

→ Setup guides: [Google AI Studio](docs/how-to-guides/how-to-setup-google-ai-studio.md) · [Vertex AI](docs/how-to-guides/how-to-setup-vertex-ai.md) · [Auth reference](docs/reference/authentication.md)

## Documentation

Full documentation follows the [Diátaxis](https://diataxis.fr/) framework. Start at the [docs landing page](docs/index.md) or browse the table below:

| Type | Document | Description |
|:-----|:---------|:------------|
| **Tutorial** | [Your First Transcription](docs/tutorials/first-transcription.md) | Get recording in 5 minutes |
| **Tutorial** | [Home Manager Setup](docs/tutorials/home-manager-setup.md) | Add agent-ear to a Home Manager flake |
| **How-to** | [How to Set Up Google AI Studio](docs/how-to-guides/how-to-setup-google-ai-studio.md) | Free API key authentication |
| **How-to** | [How to Set Up Vertex AI](docs/how-to-guides/how-to-setup-vertex-ai.md) | Full-featured GCP authentication |
| **How-to** | [How to Use the Interactive Wizard](docs/how-to-guides/how-to-use-interactive-terminal-wizard.md) | Guided setup via the terminal wizard |
| **How-to** | [How to Record Meetings](docs/how-to-guides/how-to-record-meetings.md) | Multi-speaker meetings with action items |
| **How-to** | [How to Write Your Own Prompt Template](docs/how-to-guides/how-to-write-your-own-prompt-template.md) | Custom templates for the wizard |
| **How-to** | [How to Set Up GCS Staging](docs/how-to-guides/how-to-setup-gcs-staging.md) | GCS staging (Vertex AI / files > 2 GB) |
| **How-to** | [How to Brief Users with Spoken Instructions](docs/how-to-guides/how-to-use-tts-briefing.md) | TTS briefings before recording |
| **How-to** | [How to Add agent-ear to Your Nix Flake](docs/how-to-guides/how-to-add-agent-ear-to-nix-flake.md) | Use agent-ear in your flake |
| **Explanation** | [Architecture](docs/explanation/architecture.md) | Shell/Engine design, pipeline flow, cost model |
| **Explanation** | [GCS Staging](docs/explanation/gcs-staging.md) | What staging is and when you need it |
| **Reference** | [CLI Flags & Exit Codes](docs/reference/cli.md) | Complete flag and exit code reference |
| **Reference** | [Interactive Wizard Screens](docs/reference/interactive-tui.md) | Screen-by-screen wizard specification |
| **Reference** | [Environment Variables](docs/reference/environment-variables.md) | All env vars |
| **Reference** | [Authentication](docs/reference/authentication.md) | Auth resolution & feature matrix |

See the [Changelog](CHANGELOG.md) for release history.

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

> The flake-parts module currently only exposes the `enable` option; add the package via the overlay or `packages` output above. For a turnkey setup, use the Home Manager module below.

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

→ Full guide: [Nix Consumer Integration](docs/how-to-guides/how-to-add-agent-ear-to-nix-flake.md)

## Development

```bash
# Enter dev shell
nix develop

# Run checks
nix flake check

# Build the package
nix build
```

## Community & Governance

- [Contributing Guide](CONTRIBUTING.md) — How to set up the dev environment and submit PRs
- [Security Policy](SECURITY.md) — How to report vulnerabilities safely
- [Code of Conduct](CODE_OF_CONDUCT.md) — Community guidelines

## License

Dual-licensed under MIT and Apache 2.0. See [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE).

