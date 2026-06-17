# Add agent-ear to Your Home Manager Flake

This tutorial walks you through adding agent-ear to a [Home Manager](https://github.com/nix-community/home-manager) flake. By the end, you'll have:

- The `agent-ear` binary on your PATH
- AI agent skill files installed for auto-discovery
- Voice-mode workflows ready to use

## Prerequisites

- **Nix** with flakes enabled (`experimental-features = nix-command flakes` in `nix.conf`)
- **Home Manager** managed as a flake (standalone or as a NixOS/nix-darwin module)
- A working `flake.nix` that already builds your Home Manager configuration

> [!TIP]
> Not using Home Manager yet? You can still use agent-ear with `nix run` — see the [Quick Start](../../README.md#quick-start) in the README.

## 1. Add agent-ear as a flake input

Open your `flake.nix` and add `agent-ear` to the `inputs` block:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";

    # Add this line:
    agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear";
  };
}
```

### Pin to a specific version (optional)

For reproducibility, pin to a tag or commit:

```nix
agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear/v1.1.0";
```

## 2. Apply the overlay

agent-ear needs to be available as `pkgs.agent-ear` for the Home Manager module to work. Apply the overlay where you construct your `pkgs`:

### Standalone Home Manager

```nix
{
  outputs = { nixpkgs, home-manager, agent-ear, ... }:
  let
    system = "aarch64-darwin";  # Change to your system
    pkgs = import nixpkgs {
      inherit system;
      overlays = [ agent-ear.overlays.default ];
    };
  in {
    homeConfigurations."youruser" = home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      modules = [
        agent-ear.homeManagerModules.default
        ./home.nix
      ];
    };
  };
}
```

### NixOS or nix-darwin module

If Home Manager is imported as a module in your NixOS or nix-darwin config:

```nix
{
  nixpkgs.overlays = [ inputs.agent-ear.overlays.default ];

  home-manager.sharedModules = [
    inputs.agent-ear.homeManagerModules.default
  ];
}
```

## 3. Enable agent-ear in your home configuration

In your `home.nix` (or wherever you configure Home Manager options):

```nix
{
  agent-ear.enable = true;
}
```

That's it for the basics. This single line gives you:

| What gets installed | Where |
|:--------------------|:------|
| `agent-ear` binary | `~/.nix-profile/bin/agent-ear` (on PATH) |
| Agent skill files | `~/.gemini/config/skills/agent-ear/` |
| Voice-mode workflows | `~/.gemini/config/workflows/` |

## 4. Customise options (optional)

The module exposes several options to tailor the installation:

```nix
{
  agent-ear = {
    enable = true;

    # Disable AI agent skill files if you don't use an agentic IDE
    skills.enable = false;

    # Disable voice-mode workflows
    workflows.enable = false;

    # Change the config directory (e.g. for Antigravity 2.0)
    configDir = ".agents";
  };
}
```

### Full option reference

| Option | Type | Default | Description |
|:-------|:-----|:--------|:------------|
| `agent-ear.enable` | bool | `false` | Enable agent-ear |
| `agent-ear.skills.enable` | bool | `true` | Install skill files for AI agent auto-discovery |
| `agent-ear.workflows.enable` | bool | `true` | Install voice-mode workflow files |
| `agent-ear.configDir` | string | `".gemini/config"` | Base path for skills/workflows (relative to `$HOME`) |

## 5. Rebuild and verify

Apply your configuration:

```bash
# Standalone Home Manager
home-manager switch --flake .

# NixOS
sudo nixos-rebuild switch --flake .

# nix-darwin
darwin-rebuild switch --flake .
```

Then verify everything is in place:

```bash
# Binary is available
which agent-ear
# → ~/.nix-profile/bin/agent-ear

# Skills are installed
ls ~/.gemini/config/skills/agent-ear/
# → SKILL.md

# Quick smoke test
agent-ear --help
```

## 6. Set up authentication

agent-ear needs a Gemini API connection. The fastest path:

```bash
export GOOGLE_API_KEY="your-key-from-aistudio"
```

Get a key from [Google AI Studio → API Keys](https://aistudio.google.com/apikey) in under 60 seconds.

> [!TIP]
> For persistence, add the export to your shell config or use a secrets manager. See the [full auth guide](../reference/authentication.md) for Vertex AI and other options.

## 7. Record your first note

```bash
agent-ear --non-interactive
```

Speak naturally, then press `Ctrl+C` to stop. A structured markdown note appears in your current directory.

For the full walkthrough of what happens during a recording, see [Your First Transcription](first-transcription.md).

## Complete example

Here's a minimal, self-contained `flake.nix` that sets up Home Manager with agent-ear:

```nix
{
  description = "Home configuration with agent-ear";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear";
  };

  outputs = { nixpkgs, home-manager, agent-ear, ... }:
  let
    system = "aarch64-darwin";
    pkgs = import nixpkgs {
      inherit system;
      overlays = [ agent-ear.overlays.default ];
    };
  in {
    homeConfigurations."youruser" = home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      modules = [
        agent-ear.homeManagerModules.default
        {
          home.username = "youruser";
          home.homeDirectory = "/Users/youruser";
          home.stateVersion = "24.11";

          agent-ear.enable = true;
        }
      ];
    };
  };
}
```

## What's next?

| Guide | What you'll learn |
|:------|:------------------|
| [Your First Transcription](first-transcription.md) | Full walkthrough of recording and output |
| [Set up Vertex AI](../how-to-guides/how-to-setup-vertex-ai.md) | Full-featured auth with GCS uploads |
| [TTS briefings](../how-to-guides/how-to-use-tts-briefing.md) | Have agent-ear speak instructions before recording |
| [Nix Consumer Integration](../how-to-guides/how-to-add-agent-ear-to-nix-flake.md) | Other consumption patterns (overlay, flake-parts) |
