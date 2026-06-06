# Configure GCS Staging for Large Files

> **Goal**: Configure a Google Cloud Storage staging bucket for Vertex AI users or files exceeding 2 GB.

## Prerequisites

- Vertex AI authentication configured — see [Set up Vertex AI Authentication](setup-vertex-ai.md)
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed

## Why GCS staging is needed

agent-ear handles files of any practical size. Files ≤ 100 MB are uploaded inline for speed. Larger files are automatically routed via GCS (Vertex AI) or the Gemini Files API (AI Studio, up to 2 GB). This happens transparently — you still use the same CLI commands.

```
File ≤ 100 MB   → inline upload (fastest, automatic)
File 100 MB–2 GB → Files API (AI Studio) or GCS (Vertex AI)
File > 2 GB      → GCS required (use --gcs-bucket)
```

> [!TIP]
> If you're using Google AI Studio, files up to 2 GB are handled automatically via the Gemini Files API — no GCS setup required. GCS staging is primarily needed for Vertex AI users with large files, or when you want explicit control over file staging.

## Steps

### 1. Determine if you need GCS staging

GCS staging is required when:

- You are using **Vertex AI** and need GCS staging for large files
- You want explicit control over file staging via `--gcs-bucket`

GCS staging is **not required** when:

- You're using AI Studio and your files are ≤ 2 GB (handled automatically via Files API)
- You are using **AI Studio** with files ≤2 GB (handled via the Gemini Files API)

If you don't need GCS staging, skip this guide entirely.

### 2. Create the bucket

Create a GCS bucket for staging large files:

```bash
gcloud storage buckets create gs://YOUR_PROJECT_ID-transcribe-staging \
  --location=EU \
  --uniform-bucket-level-access
```

Replace `YOUR_PROJECT_ID` with your actual project ID.

### 3. IAM permissions

The authenticated identity (your user account or service account) needs these permissions:

| Permission | Purpose |
|:-----------|:--------|
| `storage.buckets.list` | Check if the bucket exists |
| `storage.objects.create` | Upload files to the bucket |

> [!TIP]
> The built-in **Storage Object Creator** role (`roles/storage.objectCreator`) covers these permissions.

### 4. Use a custom bucket name

By default, agent-ear derives the bucket name as `{project-id}-transcribe-staging`. To use a different bucket:

**Via environment variable:**

```bash
export AGENT_EAR_GCS_BUCKET="my-custom-staging-bucket"
```

**Via CLI flag:**

```bash
agent-ear --auto --gcs-bucket my-custom-staging-bucket --video ./large-file.mp4
```

The resolution chain is: `--gcs-bucket` → `AGENT_EAR_GCS_BUCKET` → `{project-id}-transcribe-staging`.

### 5. Configure the bucket location

The default bucket location is **EU**. To change it:

```bash
export AGENT_EAR_GCS_LOCATION="US"
```

This sets the default location for the auto-derived bucket name. For manually created buckets, set the location in the `gcloud storage buckets create` command.

### 6. Verify large file support

Test with a large file:

```bash
agent-ear --auto --video ./large-presentation.mp4
```

You should see a GCS upload step in the output before the transcription begins.

## Auto-cleanup behaviour

We recommend adding a **7-day lifecycle delete rule** to your staging bucket to prevent forgotten files from accumulating costs. This means:

- Staging files are automatically deleted 7 days after upload
- No manual cleanup needed
- Ongoing storage costs are minimal

Add the lifecycle rule to your bucket:

```bash
gcloud storage buckets update gs://YOUR_BUCKET \
  --lifecycle-file=<(echo '[{"action":{"type":"Delete"},"condition":{"age":7}}]')
```
