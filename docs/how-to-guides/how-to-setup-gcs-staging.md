# Configure GCS Staging for Large Files

This how-to guide shows you how to decide if you require GCS, how to set up a GCS bucket, how to configure the bucket and test that it works with agent-ear.

> [!NOTE]
> New to staging? Read [GCS Staging](../explanation/gcs-staging.md) first for what it is and why agent-ear uses it. This guide is the procedure.

## Prerequisites

- Vertex AI authentication configured (see also [Set up Vertex AI Authentication](setup-vertex-ai.md))
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed

## Files over 2GB require GCS

Agent-ear handles files of any practical size. Files ≤ 100 MB are uploaded inline for speed. Larger files are automatically routed via GCS (Vertex AI) or the Gemini Files API (AI Studio, up to 2 GB). 

If you are using Google AI Studio, files up to 2 GB are handled automatically via the Gemini Files API no GCS setup required. GCS staging is primarily needed for Vertex AI users with large files, or when you want explicit control over file staging.

```
File ≤ 100 MB   → inline upload (fastest, automatic)
File 100 MB–2 GB → Files API (AI Studio) or GCS (Vertex AI)
File > 2 GB      → GCS required (use --gcs-bucket)
```

## Steps

### 1. Determine if you need GCS staging

Use the criteria below to decide if you need to set up a GCS staging bucket.

GCS staging is **required** if:
- You are using **Vertex AI** and transcribing files larger than 100 MB.
- You are using **Google AI Studio** and transcribing files larger than 2 GB.
- You want explicit control over where your media is staged (by passing `--gcs-bucket` or setting `AGENT_EAR_GCS_BUCKET`).

GCS staging is **not required** if:
- You are using **Google AI Studio** and all files you transcribe are 2 GB or smaller (these are handled automatically inline or via the Gemini Files API).
- You are using **Vertex AI** and only transcribe small files (100 MB or smaller) inline.

If your workflow does not require GCS staging, you can skip this guide entirely.

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

### 5. Configure the bucket location

The default bucket location is **EU**. To change it:

```bash
export AGENT_EAR_GCS_LOCATION="US"
```

This sets the default location for the auto-derived bucket name. For manually created buckets, set the location in the `gcloud storage buckets create` command.

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
