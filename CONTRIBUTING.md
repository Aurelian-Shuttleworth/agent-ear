# Contributing to agent-ear

Thanks for your interest in contributing to agent-ear! This document explains how to
get started, submit changes, and what to expect during review.

## Prerequisites

- [Nix](https://nixos.org/download/) with flakes enabled
- A GitHub account
- Familiarity with Git

> **No Python virtualenv setup required.** The Nix flake provides the complete
> development environment, including Python, all dependencies, and pre-commit hooks.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Aurelian-Shuttleworth/agent-ear.git
cd agent-ear

# Enter the development shell (installs everything via Nix)
nix develop

# Verify everything works
nix flake check
```

## Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes.** The dev shell provides all tooling:
   - `ruff` for Python linting and formatting
   - `deadnix` and `statix` for Nix linting
   - Pre-commit hooks run automatically on commit

3. **Run quality gates** before pushing:
   ```bash
   nix flake check
   ```
   This is the single source of truth for repository health. It runs linters,
   formatters, and builds the package. Do not bypass it with `--no-verify`.

4. **Open a pull request** against `main`. The CI pipeline will run
   `nix flake check` automatically.

## Code Style

Code style is enforced automatically — you do not need to memorise rules:

| Language | Tool | Configuration |
|:---------|:-----|:--------------|
| Python | `ruff` | `pyproject.toml` |
| Nix | `deadnix` + `statix` | Via `git-hooks-nix` |
| Markdown | Prose review | Manual |

## What to Contribute

- **Bug fixes** — reproduce the issue, fix it, add a note to the CHANGELOG
- **Documentation** — improvements to existing docs or new how-to guides
- **Feature requests** — open an issue first to discuss before implementing
- **Templates** — new prompt templates for the wizard (see `templates/`)

## Reporting Bugs

Please use the [bug report template](https://github.com/Aurelian-Shuttleworth/agent-ear/issues/new?template=bug_report.yml)
when filing issues. Include:

- Steps to reproduce
- Expected vs. actual behaviour
- Your environment (OS, Nix version, auth backend)
- Relevant log output

## Commit Messages

We use descriptive commit messages with a type prefix:

```
feat: add video thumbnail extraction
fix: handle empty transcription response
docs: update GCS staging guide
chore: bump flake.lock
```

## Pull Request Process

1. Ensure `nix flake check` passes locally
2. Update the CHANGELOG if your change is user-facing
3. Update documentation if your change affects user-facing behaviour
4. A maintainer will review your PR and may request changes
5. Once approved, a maintainer will merge your PR

## Questions?

If you have questions about contributing, feel free to
[open a discussion](https://github.com/Aurelian-Shuttleworth/agent-ear/discussions)
or file an issue.
