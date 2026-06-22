# ADR 004: Use Gum as the interactive Wizard framework

**Status**: Accepted
**Date**: 2026-06-22

## Context

The Shell (`agent-ear`) needs an interactive TUI for human users. The implementation lives entirely in a single bash script (`scripts/agent-ear.sh`) and uses ~48 `gum` calls for styled menus (`gum choose`), text inputs (`gum input`, `gum write`), file pickers (`gum file`), confirmations (`gum confirm`), styled output (`gum style`), and paging (`gum pager`).

Alternatives considered: `dialog`/`whiptail` (ncurses-based, rigid visual style, poor emoji support), `fzf` (fuzzy-finder optimised, no styled output or input widgets), and pure bash (`select`/`read` — functional but visually primitive, no styled output).

## Decision

Use [Gum](https://github.com/charmbracelet/gum) for all interactive Wizard components. Gum is a composable toolkit where each subcommand (`choose`, `input`, `file`, `confirm`, `style`, `pager`, `write`) handles one interaction pattern and returns the result on stdout — a natural fit for shell scripts that build up a command invocation from user choices. Its support for custom accent colours, cursor styling, and emoji labels enables a polished experience without leaving bash.

Gum is packaged in nixpkgs (`pkgs.gum`) and declared as a `runtimeInput` of the `writeShellApplication`, so users never install it manually.

## Consequences

- The Wizard's visual identity is coupled to Gum's rendering — changing frameworks would rewrite every interactive function in the script.
- The Wizard only runs where Gum runs: interactive TTYs with a capable `TERM`. This is enforced by the Shell's routing logic, which bypasses the Wizard for non-TTY contexts.
- Contributors extending the Wizard's screens must learn Gum's subcommand API, which is documented at https://github.com/charmbracelet/gum.
