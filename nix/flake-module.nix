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
              # Patch sounddevice to find portaudio at a fixed Nix store path.
              # The PyPI wheel uses ctypes.util.find_library("portaudio") which
              # relies on ldconfig / /etc/ld.so.cache — neither exists on NixOS.
              # This mirrors the nixpkgs python3Packages.sounddevice patch.
              # See: https://github.com/Aurelian-Shuttleworth/agent-ear/issues/36
              (final: prev: {
                sounddevice = prev.sounddevice.overrideAttrs (old: {
                  postInstall =
                    (old.postInstall or "")
                    + ''
                      site="$out/${final.python.sitePackages}"
                      if [ -f "$site/sounddevice.py" ]; then
                        substituteInPlace "$site/sounddevice.py" \
                          --replace-fail \
                            "for _libname in (" \
                            "for _libname in ('${pkgs.portaudio}/lib/libportaudio${pkgs.stdenv.hostPlatform.extensions.sharedLibrary}',"
                      fi
                    '';
                });
              })
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
      # Two-stage build:
      #   1. writeShellApplication → shellcheck + set -euo pipefail
      #   2. makeWrapper → inject AGENT_EAR_TEMPLATES_DIR env var
      agent-ear-unwrapped = pkgs.writeShellApplication {
        name = "agent-ear-unwrapped";
        runtimeInputs = [
          pkgs.gum
          core
        ];
        text = builtins.readFile ../scripts/agent-ear.sh;
      };

      agent-ear-script = pkgs.runCommand "agent-ear"
        {
          nativeBuildInputs = [ pkgs.makeWrapper ];
          meta.mainProgram = "agent-ear";
        }
        ''
          mkdir -p $out/bin $out/share
          cp -r ${../templates} $out/share/agent-ear-templates
          makeWrapper ${agent-ear-unwrapped}/bin/agent-ear-unwrapped $out/bin/agent-ear \
            --set AGENT_EAR_TEMPLATES_DIR "$out/share/agent-ear-templates"
        '';

      # ── Custom safety check script ─────────────────────────────
      checkGeminiSafety = pkgs.writeShellApplication {
        name = "check-gemini-safety";
        text = builtins.readFile ../scripts/check-gemini-safety.sh;
      };

      # ── Offline link checker (ADR 002) ──────────────────────────
      # lychee builds an HTTP client even in --offline mode and aborts
      # without CA certs in the Nix sandbox; point it at the nixpkgs
      # bundle so the client constructs, then no network is used.
      lycheeOffline = pkgs.writeShellApplication {
        name = "lychee-offline";
        runtimeInputs = [ pkgs.lychee ];
        text = ''
          export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
          exec lychee --offline --no-progress "$@"
        '';
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
          excludes = [ "tests/" ];
          args = [
            "-c"
            "src/pyproject.toml"
            "--quiet"
            "--skip"
            "B101,B404,B603,B607,B110"
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

        # ── Docs: internal link integrity (offline-only — ADR 002) ──
        lychee = {
          enable = true;
          entry = "${lycheeOffline}/bin/lychee-offline";
          language = "system";
          types = [ "markdown" ];
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

        # Bash dispatcher routing tests (TTY detection, flag routing)
        dispatcher = pkgs.runCommand "check-dispatcher"
          {
            nativeBuildInputs = [ pkgs.bash pkgs.coreutils ];
            env.BASH_PATH = "${pkgs.bash}/bin/bash";
          }
          ''
            bash ${../scripts/test-dispatcher.sh} ${../scripts/agent-ear.sh}
            touch $out
          '';

        # Security: deep secret scanning (CI-only — too slow for pre-commit)
        trufflehog = pkgs.runCommand "check-trufflehog"
          {
            nativeBuildInputs = [ pkgs.trufflehog ];
          }
          ''
            trufflehog filesystem ${../.} --fail
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
