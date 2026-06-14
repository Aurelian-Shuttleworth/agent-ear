# ADR 003: 4-tier upload routing strategy

**Status**: Accepted
**Date**: 2026-06-14

## Context

Media uploads need to work across two authentication backends (Vertex AI, AI Studio), a wide range of file sizes (voice memos to hour-long meetings), and both agent-driven (`--non-interactive`) and human-driven (Wizard) invocations — all without requiring cloud setup for the common case.

## Decision

`upload_media()` uses a 4-tier fallback chain to balance simplicity, capability, and authentication requirements:

1. **Explicit GCS bucket** (`--gcs-bucket`) — user-specified, highest priority
2. **Inline upload** (≤100 MB) — simplest path, no cloud setup needed
3. **GCS auto-derived** from project ID — Vertex AI users, auto-named bucket
4. **Gemini Files API** (≤2 GB, 48h TTL) — AI Studio fallback, no GCS required

The ordering ensures the most explicit user intent always wins. Each tier serves a different user profile: tier 2 covers the common case with zero config, tier 4 enables AI Studio users without GCP, and tiers 1/3 give Vertex AI users full control.

The 100 MB inline threshold was raised from 20 MB in v1.1.0 to reduce cloud staging friction for typical voice recordings (5–30 min ≈ 5–50 MB WAV).

## Considered Options

- **Single GCS path**: Rejected — forces AI Studio users to set up GCP for basic use.
- **Files API only**: Rejected — 48h TTL and 2 GB cap don't cover all use cases; Vertex AI users lose direct GCS control.
- **User chooses explicitly**: Rejected — agents calling `--non-interactive` need automatic routing without human decisions.

## Consequences

- No code path can produce a "no upload method available" error for files the API can accept.
- Changing the tier order or removing a tier would break user workflows silently — treat as a breaking change.
- The inline threshold (100 MB) is a tuning parameter that may shift with API improvements.
