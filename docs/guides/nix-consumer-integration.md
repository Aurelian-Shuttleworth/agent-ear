# Consume agent-ear in Your Nix Flake

> **Goal**: Add agent-ear as a dependency in a downstream Nix project using one of three consumption patterns.

## Prerequisites

- Nix with flakes enabled (`experimental-features = nix-command flakes` in `nix.conf`)
- An existing `flake.nix` in your project

## Steps

### 1. Add the flake input

Add agent-ear to your `flake.nix` inputs:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear";
  };
}
```

#### Pin to a specific version

For reproducibility, pin to a Git tag or commit:

```nix
# Pin to a release tag
agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear/v1.2.0";

# Pin to a specific commit
agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear/abc1234";
```

### 2. Choose a consumption pattern

agent-ear provides three ways to consume the package. Choose the one that fits your project architecture.

#### Pattern A: Direct package reference

The simplest approach — reference the package output directly.

```nix
{
  outputs = { nixpkgs, agent-ear, ... }:
  let
    system = "aarch64-darwin"; # or x86_64-linux, etc.
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [
        agent-ear.packages.${system}.agent-ear
      ];
    };
  };
}
```

#### Pattern B: Overlay

Apply the overlay to make `pkgs.agent-ear` available everywhere in your nixpkgs instance.

```nix
{
  outputs = { nixpkgs, agent-ear, ... }:
  let
    system = "aarch64-darwin";
    pkgs = import nixpkgs {
      inherit system;
      overlays = [ agent-ear.overlays.default ];
    };
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [ pkgs.agent-ear ];
    };
  };
}
```

This is useful when you want agent-ear available as a regular nixpkgs package across your entire configuration.

#### Pattern C: FlakeModule (flake-parts)

For projects using [flake-parts](https://flake.parts), import the module and enable it declaratively:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    agent-ear.url = "github:Aurelian-Shuttleworth/agent-ear";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-darwin" ];

      imports = [
        inputs.agent-ear.flakeModules.agent-ear
      ];

      # Enable agent-ear
      agent-ear.enable = true;
    };
}
```

### 3. Home Manager integration

To include agent-ear in a Home Manager profile:

```nix
# home.nix or home-manager module
{ inputs, pkgs, ... }:
{
  home.packages = [
    inputs.agent-ear.packages.${pkgs.system}.agent-ear
  ];
}
```

Or if you've applied the overlay to your nixpkgs:

```nix
{ pkgs, ... }:
{
  home.packages = [ pkgs.agent-ear ];
}
```

### 4. Verify the installation

After rebuilding your environment:

```bash
# Check the binary is available
which agent-ear

# Confirm version
agent-ear --help
```

## Available packages

The flake exposes two packages per system:

| Package | Description |
|:--------|:------------|
| `agent-ear` (default) | Main entry point — handles routing and interactive wizard |
| `agent-ear-core` | Python backend — the pipeline that agents and scripts call |

Reference them as `inputs.agent-ear.packages.${system}.<name>`.

## Next steps

- [Set up Google AI Studio Authentication](setup-google-ai-studio.md) — quickest path to get transcribing
- [Set up Vertex AI Authentication](setup-vertex-ai.md) — full feature set with GCS support
