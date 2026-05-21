# nix/flake-module.nix
#
# Self-contained flake-parts module for agent-ear.
# All packaging, containers, checks, and devShell in one file.
# Zero external dependencies on company infrastructure.
{
  inputs,
  self,
  lib,
  ...
}:
{
  # ── Reusable flake module for downstream consumers ──────────────
  flake.flakeModules.agent-ear =
    {
      config,
      lib,
      ...
    }:
    {
      options.agent-ear = {
        enable = lib.mkEnableOption "agent-ear voice capture & transcription tool";
      };

      # Consumers wire this up in their own perSystem/home.packages
    };

  # ── Overlay for nixpkgs consumers ───────────────────────────────
  flake.overlays.default = final: _prev: {
    agent-ear = self.packages.${final.system}.agent-ear;
  };

  # ── Per-system outputs ──────────────────────────────────────────
  perSystem =
    {
      pkgs,
      lib,
      system,
      ...
    }:
    let
      # ── Python environment via uv2nix ─────────────────────────
      workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
        workspaceRoot = ../src;
      };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      pythonSet =
        (pkgs.callPackage inputs.pyproject-nix.build.packages {
          python = pkgs.python313;
        }).overrideScope
          (
            lib.composeManyExtensions [
              inputs.pyproject-build-systems.overlays.wheel
              overlay
            ]
          );

      venv = pythonSet.mkVirtualEnv "agent-ear-env" workspace.deps.default;

      # ── Native library paths ──────────────────────────────────
      binPath = lib.makeBinPath [
        pkgs.ffmpeg
        pkgs.yt-dlp
      ];
      libPath = lib.makeLibraryPath [
        pkgs.portaudio
        pkgs.libsndfile
      ];
      libVar = if pkgs.stdenv.isDarwin then "DYLD_LIBRARY_PATH" else "LD_LIBRARY_PATH";

      # ── Binary 1: agent-ear-core (Python backend) ─────────────
      core = pkgs.runCommand "agent-ear-core"
        {
          nativeBuildInputs = [ pkgs.makeWrapper ];
          meta.mainProgram = "agent-ear-core";
        }
        ''
          mkdir -p $out/bin
          makeWrapper ${venv}/bin/agent-ear $out/bin/agent-ear-core \
            --prefix PATH : "${binPath}" \
            --prefix ${libVar} : "${libPath}" \
            --unset PYTHONPATH \
            --unset PYTHONHOME
        '';

      # ── Binary 2: agent-ear-interactive (Gum TUI) ─────────────
      interactive = pkgs.writeShellApplication {
        name = "agent-ear-interactive";
        runtimeInputs = [
          pkgs.gum
          core
        ];
        text = builtins.readFile ../scripts/agent-ear-interactive.sh;
      };

      # ── Binary 3: agent-ear (dispatcher) ───────────────────────
      dispatcher = pkgs.writeShellApplication {
        name = "agent-ear";
        runtimeInputs = [
          core
          interactive
        ];
        text = ''
          # Pass-through to core for flags that bypass interactive mode
          for arg in "$@"; do
            case "$arg" in
              --auto|--help|-h)
                exec agent-ear-core "$@"
                ;;
            esac
          done

          # Pass-through to core if stdin is not a TTY (piped/automated)
          if [[ ! -t 0 ]]; then
            exec agent-ear-core "$@"
          fi

          # Interactive mode
          exec agent-ear-interactive "$@"
        '';
        meta.mainProgram = "agent-ear";
      };

      # ── OCI container image ────────────────────────────────────
      container = pkgs.dockerTools.buildLayeredImage {
        name = "ghcr.io/aurelianshuttleworth/agent-ear";
        tag = "latest";
        contents = [
          dispatcher
          pkgs.bashInteractive
          pkgs.coreutils
          pkgs.cacert
        ];
        config = {
          Cmd = [ "${dispatcher}/bin/agent-ear" "--auto" ];
          Env = [
            "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
          ];
        };
      };
    in
    {
      # ── Packages ────────────────────────────────────────────────
      packages = {
        default = dispatcher;
        agent-ear = dispatcher;
        agent-ear-core = core;
        agent-ear-interactive = interactive;
        container = container;
      };

      # ── Checks (self-contained quality gates) ───────────────────
      checks = {
        # Verify the package builds
        build = dispatcher;

        # Dead code detection
        deadnix = pkgs.runCommand "check-deadnix" { nativeBuildInputs = [ pkgs.deadnix ]; } ''
          deadnix --fail ${../.}
          touch $out
        '';

        # Static Nix linting
        statix = pkgs.runCommand "check-statix" { nativeBuildInputs = [ pkgs.statix ]; } ''
          statix check ${../.}
          touch $out
        '';
      };

      # ── DevShell ────────────────────────────────────────────────
      devShells.default = pkgs.mkShell {
        packages = [
          pkgs.uv
          pkgs.gum
          pkgs.ffmpeg
          pkgs.yt-dlp
          pkgs.portaudio
          pkgs.libsndfile

          # Nix quality tools
          pkgs.deadnix
          pkgs.statix
          pkgs.nixfmt-rfc-style
        ];
        shellHook = ''
          unset PYTHONPATH
          unset PYTHONHOME
          echo "🎙️  agent-ear dev shell"
        '';
      };
    };
}
