# How to Set Up GCS Staging for Large Files

This how-to guide shows you how to configure a Google Cloud Storage staging bucket for Vertex AI users or files exceeding 2 GB.

> [!NOTE]
> New to staging? You may find it helpful to read [GCS Staging](../explanation/gcs-staging.md) first for what it is and why agent-ear uses it.

## Prerequisites

- Vertex AI authentication configured — see [Set up Vertex AI Authentication](how-to-setup-vertex-ai.md)
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
agent-ear --non-interactive --gcs-bucket my-custom-staging-bucket --video ./large-file.mp4
```

The resolution chain is: `--gcs-bucket` → `AGENT_EAR_GCS_BUCKET` → `{project-id}-transcribe-staging`.

### 5. Choose the bucket location

agent-ear stages files into an **existing** bucket — it does not create buckets for you, so set the region when you create the bucket in step 2 via the `--location` flag:

```bash
gcloud storage buckets create gs://YOUR_PROJECT_ID-transcribe-staging \
  --location=US \
  --uniform-bucket-level-access
```

Pick the region closest to you or one that matches your data-residency requirements (e.g. `EU`, `US`, `ASIA`).

### 6. Verify large file support

Test with a large file:

```bash
agent-ear --non-interactive --video ./large-presentation.mp4
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
