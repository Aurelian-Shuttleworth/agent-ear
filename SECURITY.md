# Security Policy

## Supported Versions

| Version | Supported          |
|:--------|:-------------------|
| 1.1.x   | ✅ Current release |
| < 1.1   | ❌ Not supported   |

## Reporting a Vulnerability

If you discover a security vulnerability in agent-ear, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

### Preferred: GitHub Private Vulnerability Reporting

1. Go to the [Security tab](https://github.com/Aurelian-Shuttleworth/agent-ear/security)
   of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details and submit

### Alternative: Email

If GitHub Private Vulnerability Reporting is not available, contact the
lead maintainer via their GitHub profile listed in [MAINTAINERS.md](MAINTAINERS.md).

## What Counts as a Security Issue

agent-ear is a CLI tool that handles audio recordings and communicates with
Google's Gemini API. Security-relevant issues include:

- **Credential exposure** — API keys, tokens, or credentials leaked in logs,
  output files, or error messages
- **Recording data leakage** — Audio or transcription data sent to unintended
  destinations
- **Command injection** — Unsanitised input leading to shell command execution
- **Path traversal** — Output files written outside the intended directory
- **Dependency vulnerabilities** — Known CVEs in direct dependencies

Issues that are **not** security vulnerabilities:

- Transcription quality or accuracy problems
- Feature requests
- General bugs that do not have a security impact

## Disclosure Timeline

- **Acknowledgement**: Within 48 hours of report
- **Initial assessment**: Within 7 days
- **Fix target**: Within 90 days of confirmed vulnerability
- **Public disclosure**: After fix is released, or 90 days after report,
  whichever comes first

## Security Strengths

- **Reproducible builds** via Nix flake — supply chain integrity by default
- **No persistent storage of credentials** — API keys are read from environment
  variables or `gcloud` config, never stored by agent-ear
- **Minimal permissions** — the tool requires only microphone access and
  network access to Google APIs
