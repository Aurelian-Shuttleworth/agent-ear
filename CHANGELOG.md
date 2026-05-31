<!-- REVIEW: Lara — are the release dates correct? I used 2026-05-31 for v1.1.0 and a placeholder for v1.0.0. -->

# Changelog

All notable changes to agent-ear are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-05-31

### Added

- **Gemini Files API support** — AI Studio users can now upload files up to 2 GB via the Gemini Files API (48-hour temporary storage with async upload polling). No GCS bucket setup required.
- **Thinking level controls** — New `--thinking-level` flag (`minimal` / `low` / `medium` / `high`) and `AGENT_EAR_THINKING_LEVEL` environment variable for controlling transcription model reasoning depth. Auto-resolved from prompt complexity and audio duration when not set.
- **Dynamic token budgets** — Output token limits now scale with recording duration (~200 tokens per minute of speech, floor 8192, cap 65536). Video transcription defaults to 32768.
- **Prompt validator hints** — The LLM-as-a-Judge validator now emits `thinking_level` and `extra_tokens` hints that auto-configure the transcription model for optimal quality.
- **Meeting Mode** — Interactive wizard mode for multi-speaker transcription with named or numbered speaker identification, action items extraction, and notable quotes.
- **Interactive terminal wizard** — Gum-based TUI wrapper (`agent-ear-interactive`) providing 7 modes, configuration screens, and advanced options for human users.
- **`--max-tokens` flag** — Explicit override for the auto-scaled output token limit.

### Changed

- **Default model** upgraded from `gemini-3.1-flash-lite-preview` to `gemini-3.5-flash` across all pipelines (validation, transcription, video).
- **Inline upload threshold** raised from 20 MB to 100 MB, reducing the need for cloud staging.
- **Upload routing** rewritten with a 4-tier strategy:
  1. Explicit GCS bucket (user-specified `--gcs-bucket`)
  2. Inline upload (≤100 MB)
  3. GCS auto-derived from project ID (Vertex AI)
  4. Gemini Files API fallback (AI Studio, ≤2 GB)
- **Location resolution** now follows a priority chain: `--location` flag → `GOOGLE_CLOUD_LOCATION` env var → `gcloud config` → `global`.

### Removed

- **GCS auto-provisioning** — Buckets are no longer created automatically. Users must create staging buckets manually before use. See the [GCS staging guide](docs/guides/setup-gcs-staging.md).

### Fixed

- Video download warning now correctly displays the 100 MB threshold instead of the stale 20 MB value.

---

## [1.0.0] — 2025-XX-XX

<!-- REVIEW: Lara — please fill in the actual v1.0.0 release date. -->

Initial release.
