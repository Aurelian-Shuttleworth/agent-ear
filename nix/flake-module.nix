# nix/flake-module.nix
#
# Self-contained flake-parts module for agent-ear.
# All packaging, checks, and devShell in one file.
# Zero external dependencies on company infrastructure.
{
  inputs,
  self,
  ...
}:
{
  # ── Top-level flake outputs ──────────────────────────────────────
  flake = {
    # Reusable flake module for downstream consumers
    flakeModules.agent-ear =
      {
        lib,
        ...
      }:
      {
        options.agent-ear = {
          enable = lib.mkEnableOption "agent-ear voice capture & transcription tool";
        };

        # Consumers wire this up in their own perSystem/home.packages
      };

    # Home Manager modules
    homeManagerModules.default = self.homeManagerModules.agent-ear;
    homeManagerModules.agent-ear =
      {
        config,
        lib,
        pkgs,
        ...
      }:
      let
        cfg = config.agent-ear;
      in
      {
        options.agent-ear = {
          enable = lib.mkEnableOption "agent-ear voice capture & transcription";

          skills.enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Install agent-ear skill for AI agent auto-discovery.";
          };

          workflows.enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Install agent-ear workflows (e.g., voice-mode).";
          };

          configDir = lib.mkOption {
            type = lib.types.str;
            default = ".gemini/config";
            description = ''
              Base directory for skill/workflow placement (relative to $HOME).
              Change to ".agents" when migrating to the Antigravity 2.0 path.
            '';
          };
        };

        config = lib.mkIf cfg.enable {
          # Binary in PATH (requires overlay applied to pkgs)
          home.packages = [ pkgs.agent-ear ];

          # Skill files for AI agent auto-discovery
          home.file = lib.mkMerge [
            (lib.mkIf cfg.skills.enable {
              "${cfg.configDir}/skills/agent-ear/SKILL.md" = {
                source = ../nix/resources/skills/agent-ear/SKILL.md;
              };
              "${cfg.configDir}/skills/agent-ear-capture/SKILL.md" = {
                source = ../nix/resources/skills/agent-ear-capture/SKILL.md;
              };
              "${cfg.configDir}/skills/agent-ear-briefing/SKILL.md" = {
                source = ../nix/resources/skills/agent-ear-briefing/SKILL.md;
              };
              "${cfg.configDir}/skills/agent-ear-video/SKILL.md" = {
                source = ../nix/resources/skills/agent-ear-video/SKILL.md;
              };
            })
            (lib.mkIf cfg.workflows.enable {
              "${cfg.configDir}/workflows/voice-mode.md" = {
                source = ../nix/resources/workflows/voice-mode.md;
              };
              "${cfg.configDir}/workflows/voice-capture.md" = {
                source = ../nix/resources/workflows/voice-capture.md;
              };
            })
          ];
        };
      };

    # Overlay for nixpkgs consumers
    overlays.default = final: _prev: {
      agent-ear = self.packages.${final.system}.agent-ear;
    };
  };

  # ── Per-system outputs ──────────────────────────────────────────
  perSystem =
    {
      pkgs,
      lib,
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
      testVenv = pythonSet.mkVirtualEnv "agent-ear-test-env" {
        agent-ear = [ "test" ];
      };

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
    in
    {
      # ── Packages ────────────────────────────────────────────────
      packages = {
        default = dispatcher;
        agent-ear = dispatcher;
        agent-ear-core = core;
        agent-ear-interactive = interactive;
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

        # Python test suite (excludes integration tests)
        pytest = pkgs.runCommand "check-pytest"
          {
            nativeBuildInputs = [ testVenv ];
            buildInputs = [
              pkgs.portaudio
              pkgs.libsndfile
            ];
            env.${libVar} = libPath;
          }
          ''
            export PYTHONPATH="${../src}:$PYTHONPATH"
            python -m pytest ${../src}/tests/ \
              --rootdir=${../src} \
              -c ${../src}/pyproject.toml \
              -m "not integration" \
              --tb=short \
              -q \
              --no-header \
              -p no:cacheprovider
            touch $out
          '';

        # Python linting + formatting
        ruff = pkgs.runCommand "check-ruff" { nativeBuildInputs = [ pkgs.ruff ]; } ''
          ruff check ${../src}
          ruff format --check ${../src}
          touch $out
        '';

        # Shell script linting
        shellcheck = pkgs.runCommand "check-shellcheck" { nativeBuildInputs = [ pkgs.shellcheck ]; } ''
          shellcheck ${../scripts}/*.sh
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

          # Python quality tools
          pkgs.ruff

          # Shell quality tools
          pkgs.shellcheck
        ];
        shellHook = ''
          unset PYTHONPATH
          unset PYTHONHOME
          echo "🎙️  agent-ear dev shell"
        '';
      };
    };
}
