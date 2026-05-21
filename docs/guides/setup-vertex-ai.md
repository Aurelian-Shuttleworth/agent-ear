# Set up Vertex AI Authentication (Full Features)

> **Goal**: Configure a GCP project with Application Default Credentials to unlock the complete agent-ear feature set, including GCS uploads for large files.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed

## Steps

### 1. Create or select a GCP project

If you don't have a project, create one at [console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).

Note your **Project ID** (not the display name) — you'll need it in the next steps.

### 2. Enable the Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
```

### 3. Authenticate with Application Default Credentials

```bash
gcloud auth application-default login
```

This opens a browser to complete the OAuth flow and stores credentials that the Google client libraries use automatically.

### 4. Set your project

agent-ear resolves the project ID via a 3-tier chain:

```
--project-id flag → GOOGLE_CLOUD_PROJECT env var → gcloud config
```

Choose whichever method suits your workflow:

**Option A: gcloud config (recommended for single-project setups)**

```bash
gcloud config set project YOUR_PROJECT_ID
```

**Option B: Environment variable (good for multi-project or CI)**

```bash
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
```

**Option C: CLI flag (per-invocation override)**

```bash
agent-ear --auto --project-id YOUR_PROJECT_ID
```

### 5. Verify with a test recording

```bash
agent-ear --auto --output-format markdown
```

Look for the Vertex AI backend confirmation in the output. The transcription should complete and produce a markdown file in the current directory.

### 6. (Optional) Set your preferred region

By default, agent-ear uses `global` as the Vertex AI location. To use a specific region:

**Via environment variable:**

```bash
export GOOGLE_CLOUD_LOCATION="europe-west4"
```

**Via gcloud config:**

```bash
gcloud config set compute/region europe-west4
```

The resolution chain for location is: `GOOGLE_CLOUD_LOCATION` → `gcloud config get-value compute/region` → `global`.

## Next steps

- [Configure GCS Staging for Large Files](setup-gcs-staging.md) — required for audio/video files >20 MB
- [Brief Users with Spoken Instructions](tts-briefing.md) — use TTS to speak instructions before recording
