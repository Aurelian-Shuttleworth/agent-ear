# How to Set Up Google AI Studio Authentication

> **Goal**: Get agent-ear transcribing in under 5 minutes using a free API key — no GCP project required.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))

## Steps

### 1. Get an API key

Visit [Google AI Studio → API Keys](https://aistudio.google.com/apikey) and click **Create API key**.

> [!TIP]
> You don't need to create a GCP project. Google AI Studio provides a free-tier key that works immediately.

### 2. Export the key

Set the key in your shell environment:

```bash
export GOOGLE_API_KEY="AIza..."
```

To persist it, add it to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) or use a secrets manager like `direnv` with `.envrc`:

```bash
# .envrc (kept out of version control via .gitignore)
export GOOGLE_API_KEY="AIza..."
```

### 3. Verify with a test recording

Run a quick freeform transcription to confirm everything works:

```bash
agent-ear --non-interactive --output-format markdown
```

You should see output confirming the transcription model and a resulting markdown file in the current directory.

### 4. Understand the limitations

Google AI Studio keys provide most features but have important restrictions:

| Feature | AI Studio | Vertex AI |
|:--------|:---------:|:---------:|
| Voice recording & transcription | ✅ | ✅ |
| TTS briefing | ✅ | ✅ |
| Prompt validation | ✅ | ✅ |
| Video / YouTube transcription | ✅ | ✅ |
| Files ≤ 2 GB | ✅ | ✅ |
| Files > 2 GB (GCS staging) | ❌ | ✅ |
| All model variants | ⚠️ Subset | ✅ |

AI Studio supports files up to 2 GB (small files go inline, larger ones use the Gemini Files API — all transparent and at no additional cost). For files exceeding 2 GB, you'll need Vertex AI authentication with GCS staging. See [Set up Vertex AI Authentication](how-to-setup-vertex-ai.md) and [Configure GCS Staging for Large Files](how-to-setup-gcs-staging.md).

## How it works

When `agent-ear` starts, it resolves authentication in this order:

1. **Vertex AI** — if a GCP project ID is available (via `--project-id`, `GOOGLE_CLOUD_PROJECT`, or `gcloud config`)
2. **Google AI Studio** — if `GOOGLE_API_KEY` is set
3. **Error** — no credentials found

Since AI Studio doesn't require a project ID, setting `GOOGLE_API_KEY` without any GCP configuration gives you the AI Studio backend automatically.
