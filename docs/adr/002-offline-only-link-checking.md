# ADR 002: Offline-only link checking in the quality gate

**Status**: Accepted
**Date**: 2026-06-12

## Context

A documentation rename (`docs/guides/` → `docs/how-to-guides/` with new filenames) merged with ~20 internal links left pointing at the old paths across README, the docs index, tutorials, and guide cross-references. Nothing in `nix flake check` or CI validates links, so the breakage shipped silently and was found by hand days later.

## Decision

Add an offline link checker (lychee with `--offline`) as a pre-commit hook in `nix/flake-module.nix`, so it runs in `nix flake check` and CI like every other gate. It validates internal/relative links only.

External URL checking was deliberately excluded: external checks are network-dependent, flaky in CI (rate limits, transient outages), and need allowlist maintenance. The failure mode we actually suffered — renames breaking internal links — is fully covered offline.

## Consequences

- File renames that break relative links fail at commit time instead of shipping.
- Dead *external* URLs are not caught; checking them stays a manual (or future, separately-gated) concern. Do not "fix" this by enabling online mode in the shared gate — it will make CI flaky.
- Contributors get link validation for free via the existing `nix develop` pre-commit setup.
