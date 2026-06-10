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
      config,
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

      # ── Binary 2: agent-ear (Gum TUI & Dispatcher) ────────────
      agent-ear-script = pkgs.writeShellApplication {
        name = "agent-ear";
        runtimeInputs = [
          pkgs.gum
          core
        ];
        text = builtins.readFile ../scripts/agent-ear.sh;
        meta.mainProgram = "agent-ear";
      };

      # ── Custom safety check script ─────────────────────────────
      checkGeminiSafety = pkgs.writeShellApplication {
        name = "check-gemini-safety";
        text = builtins.readFile ../scripts/check-gemini-safety.sh;
      };
    in
    {
      # ── Packages ────────────────────────────────────────────────
      packages = {
        default = agent-ear-script;
        agent-ear = agent-ear-script;
        agent-ear-core = core;
      };

      # ── Pre-commit hooks (run pre-commit + CI via nix flake check) ─
      pre-commit.settings.hooks = {
        # ── Nix linters ──
        deadnix.enable = true;
        statix.enable = true;

        # ── Python linting + formatting ──
        ruff-check = {
          enable = true;
          entry = "${pkgs.ruff}/bin/ruff check --config src/pyproject.toml --fix";
          language = "system";
          types = [ "python" ];
          pass_filenames = true;
        };
        ruff-format = {
          enable = true;
          entry = "${pkgs.ruff}/bin/ruff format --config src/pyproject.toml";
          language = "system";
          types = [ "python" ];
          pass_filenames = true;
        };

        # ── Shell linting ──
        shellcheck = {
          enable = true;
          excludes = [ "\\.envrc$" ];
        };

        # ── Security: Python static analysis ──
        bandit = {
          enable = true;
          entry = "${pkgs.python313Packages.bandit}/bin/bandit";
          language = "system";
          types = [ "python" ];
          args = [
            "-c"
            "src/pyproject.toml"
            "--quiet"
            "--skip"
            "B404,B603,B607,B110"
          ];
        };

        # ── Security: secret leak detection ──
        detect-secrets = {
          enable = true;
          entry = "${pkgs.detect-secrets}/bin/detect-secrets-hook";
          language = "system";
          types = [ "text" ];
          args = [
            "--baseline"
            ".secrets.baseline"
          ];
        };

        # ── Custom: Gemini safety_settings enforcement ──
        gemini-safety-settings = {
          enable = true;
          entry = "${checkGeminiSafety}/bin/check-gemini-safety";
          language = "system";
          types = [ "python" ];
          pass_filenames = true;
        };
      };

      # ── Checks (CI-only gates + pre-commit) ─────────────────────
      checks = {
        # Verify the package builds
        build = agent-ear-script;

        # Python test suite (excludes integration tests)
        pytest = pkgs.runCommand "check-pytest"
          {
            nativeBuildInputs = [ testVenv ];
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

      };

      # ── DevShell ────────────────────────────────────────────────
      # inputsFrom pulls in all hook tool deps (ruff, deadnix, statix,
      # shellcheck, bandit, detect-secrets) dynamically from git-hooks.
      devShells.default = pkgs.mkShell {
        inputsFrom = [ config.pre-commit.devShell ];
        packages = [
          agent-ear-script
          testVenv
          pkgs.uv
          pkgs.gum
          pkgs.ffmpeg
          pkgs.yt-dlp
          pkgs.portaudio
          pkgs.libsndfile
          pkgs.nixfmt
        ];
        shellHook = ''
          unset PYTHONPATH
          unset PYTHONHOME

          # Symlink the Nix venv so IDE tools (Pyrefly, Pylance, PyCharm)
          # auto-discover project dependencies without manual config.
          # Root-level for general tools, src/.venv for Pyrefly (which
          # discovers project root via src/pyproject.toml).
          ln -sfn "${testVenv}" .venv
          ln -sfn "${testVenv}" src/.venv

          echo "🎙️  agent-ear dev shell"
        '';
      };
    };
}
