---
tags:
  - reference
  - environment-variables
  - agent-ear
creation_date: 2026-05-21
status: active
category: Resource
---

# Environment Variables

> [!NOTE] Diátaxis: Reference
> This is **information-oriented** documentation. It describes every environment variable that agent-ear reads, in what order, and with what fallback behaviour.

## Overview

agent-ear reads environment variables as the second tier in its configuration priority chain:

```
CLI flag → Environment variable → Auto-detected (gcloud) → Default
```

Variables are grouped by function: **authentication**, **project configuration**, and **output**.

---

## Authentication Variables

### `GOOGLE_API_KEY`

| Property | Value |
|:---------|:------|
| **Purpose** | Authenticates with Google AI Studio (non-Vertex backend) |
| **Default** | — (not set) |
| **Required** | One of `GOOGLE_API_KEY` or a resolved GCP project is required |
| **Used by** | `genai.Client(api_key=...)` |

The fallback authentication method. When no GCP project can be resolved (via `--project-id`, `GOOGLE_CLOUD_PROJECT`, or `gcloud config`), agent-ear falls back to this key for Google AI Studio mode.

> [!WARNING]
> AI Studio mode **cannot** use GCS staging. Files up to 2 GB can be uploaded via the Gemini Files API, but files exceeding 2 GB require Vertex AI mode with GCS.

**Example:**

```bash
export GOOGLE_API_KEY="AIza..."
agent-ear --non-interactive --prompt "Quick transcription"
```

---

### `GOOGLE_APPLICATION_CREDENTIALS`

| Property | Value |
|:---------|:------|
| **Purpose** | Path to a service account JSON key file for Application Default Credentials (ADC) |
| **Default** | — (not set; ADC uses `gcloud auth application-default login` credentials) |
| **Required** | No |
| **Used by** | Google Cloud client libraries (implicit ADC resolution) |

Only needed in environments where `gcloud auth application-default login` is not available — typically CI/CD pipelines, Docker containers, or headless servers.

In most development setups, ADC resolves credentials automatically from `gcloud` without this variable.

**Example:**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
agent-ear --non-interactive --project-id my-project
```

---

### `GOOGLE_CLOUD_PROJECT`

| Property | Value |
|:---------|:------|
| **Purpose** | Google Cloud project ID for Vertex AI mode |
| **Default** | Resolved from `gcloud config get-value project` |
| **Required** | No (auto-detected from gcloud if not set) |
| **CLI equivalent** | `--project-id` |
| **Used by** | `genai.Client(vertexai=True, project=...)` |

Setting a project ID (by any method) activates **Vertex AI mode**, which enables GCS staging for large files and access to all Vertex-hosted models.

**Resolution chain:**

```
--project-id → GOOGLE_CLOUD_PROJECT → gcloud config get-value project → None
```

If all three resolve to `None`, agent-ear falls back to AI Studio mode (requires `GOOGLE_API_KEY`).

**Example:**

```bash
export GOOGLE_CLOUD_PROJECT="my-gcp-project"
agent-ear --non-interactive  # Uses Vertex AI mode automatically
```

---

### `GOOGLE_CLOUD_LOCATION`

| Property | Value |
|:---------|:------|
| **Purpose** | Gemini API region for Vertex AI |
| **Default** | Resolved from `gcloud config get-value compute/region`, then falls back to `global` |
| **Required** | No |
| **CLI equivalent** | `--location` |
| **Used by** | `genai.Client(vertexai=True, location=...)` |

Controls which regional endpoint serves Gemini API requests. The `global` default routes to the nearest available region.

**Resolution chain:**

```
--location → GOOGLE_CLOUD_LOCATION → gcloud config get-value compute/region → global
```

**Example:**

```bash
export GOOGLE_CLOUD_LOCATION="us-central1"
agent-ear --non-interactive --project-id my-project
```

---

## Output Variables

### `AGENT_EAR_OUTPUT_DIR`

| Property | Value |
|:---------|:------|
| **Purpose** | Default directory for output files (transcripts, JSON reports) |
| **Default** | Current working directory (`.`) |
| **Required** | No |
| **CLI equivalent** | `--output-dir` |

When set, all output files are written to this directory. The directory is created if it does not exist. The `--output-dir` CLI flag takes precedence.

**Example:**

```bash
export AGENT_EAR_OUTPUT_DIR="$HOME/transcripts"
agent-ear --non-interactive  # Output written to ~/transcripts/
```

---

## Reasoning Variables

### `AGENT_EAR_THINKING_LEVEL`

| Property | Value |
|:---------|:------|
| **Purpose** | Override reasoning depth for the transcription model |
| **Default** | Auto-determined from prompt complexity and audio duration |
| **Required** | No |
| **CLI equivalent** | `--thinking-level` |
| **Allowed values** | `minimal`, `low`, `medium`, `high` |

Controls how much internal reasoning (chain-of-thought) the transcription model performs. Higher levels improve quality for complex prompts (multi-speaker analysis, cross-referencing) at the cost of increased latency and token usage.

When not set, the thinking level is resolved automatically via a priority chain:

```
--thinking-level flag → AGENT_EAR_THINKING_LEVEL → Prompt validator hint → Duration-based default
```

Duration-based defaults: ≤2 min → `low`, 2–10 min → `medium`, >10 min → `high`. Text-heavy video with `--high-res` promotes to `high` regardless.

**Example:**

```bash
export AGENT_EAR_THINKING_LEVEL="high"
agent-ear --non-interactive --prompt-file complex-analysis.md
```

---

## GCS Variables

### `AGENT_EAR_GCS_BUCKET`

| Property | Value |
|:---------|:------|
| **Purpose** | GCS bucket name for staging media files (Vertex AI, or files > 2 GB) |
| **Default** | `{project}-transcribe-staging` (derived from the resolved project ID) |
| **Required** | No |
| **CLI equivalent** | `--gcs-bucket` |
| **Requires** | Vertex AI mode (a resolved project ID) |

The bucket must exist before use. See [How to Set Up GCS Staging](../how-to-guides/how-to-setup-gcs-staging.md) for creation instructions. The default naming convention uses the project ID as a prefix to ensure uniqueness.

**Example:**

```bash
export AGENT_EAR_GCS_BUCKET="my-custom-staging-bucket"
agent-ear --non-interactive --video ./large-video.mp4
```

---

### `AGENT_EAR_GCS_LOCATION`

| Property | Value |
|:---------|:------|
| **Purpose** | Geographic region for GCS bucket creation |
| **Default** | `EU` |
| **Required** | No |

Controls where the GCS staging bucket is physically located. Only relevant during initial bucket creation — has no effect if the bucket already exists.

> [!TIP]
> Set this to match your primary data residency requirements. Common values: `EU`, `US`, `ASIA`.

**Example:**

```bash
export AGENT_EAR_GCS_LOCATION="US"
agent-ear --non-interactive --video ./large-recording.mp4 --project-id my-project
```

---

## Quick Reference Table

| Variable | Purpose | Default | Required? |
|:---------|:--------|:--------|:----------|
| `GOOGLE_API_KEY` | AI Studio auth (fallback) | — | One of this or GCP project |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI | `gcloud config` | — |
| `GOOGLE_CLOUD_LOCATION` | Gemini region | `gcloud config` → `global` | — |
| `GOOGLE_APPLICATION_CREDENTIALS` | ADC service account key path | — | — |
| `AGENT_EAR_OUTPUT_DIR` | Default output directory | Current directory | — |
| `AGENT_EAR_GCS_BUCKET` | GCS staging bucket name | `{project}-transcribe-staging` | — |
| `AGENT_EAR_GCS_LOCATION` | GCS bucket region | `EU` | — |
| `AGENT_EAR_THINKING_LEVEL` | Reasoning depth override | Auto (duration-based) | — |

## See Also

- [CLI Reference](cli.md) — Complete CLI flag reference
- [Authentication](authentication.md) — Auth backend selection and troubleshooting
