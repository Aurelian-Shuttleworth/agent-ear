# Configure GCS Staging for Large Files

> **Goal**: Enable transcription of audio and video files larger than 20 MB by configuring a Google Cloud Storage staging bucket.

## Prerequisites

- Vertex AI authentication configured — see [Set up Vertex AI Authentication](setup-vertex-ai.md)
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed

## Why GCS staging is needed

The Gemini API accepts files inline up to **20 MB**. For anything larger, agent-ear uploads the file to a GCS bucket and passes the `gs://` URI to Gemini instead. This happens transparently — you still use the same CLI commands.

```
File ≤20 MB → inline upload → Gemini API
File >20 MB → GCS upload → gs:// URI → Gemini API
```

> [!NOTE]
> GCS staging is only available with the Vertex AI backend. Google AI Studio keys cannot access GCS. If you're using an AI Studio key, files over 20 MB will fail with an error.

## Steps

### 1. Let agent-ear auto-provision (interactive mode)

The simplest path. Run agent-ear **without** `--auto` on a large file:

```bash
agent-ear --video ./long-meeting.mp4
```

If no bucket exists, agent-ear will prompt you:

```
📦 GCS bucket 'your-project-transcribe-staging' not found.
   Location: EU
   Lifecycle: auto-delete staging files after 7 days

Create this bucket now? [y/N]:
```

Confirm with `y` and the bucket is created with a **7-day auto-delete lifecycle rule** — staging files are cleaned up automatically.

> [!IMPORTANT]
> Auto-provisioning only works in interactive mode (no `--auto` flag). In `--auto` mode, agent-ear errors instead of prompting, since bucket creation could incur costs.

### 2. Or create the bucket manually

If you prefer to create the bucket yourself, or need it for `--auto` mode:

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
| `storage.buckets.create` | Create the staging bucket (auto-provisioning only) |
| `storage.buckets.list` | Check if the bucket already exists |
| `storage.objects.create` | Upload files to the bucket |
| `serviceusage.services.get` | Check if Cloud Storage API is enabled |
| `serviceusage.services.enable` | Enable Cloud Storage API (auto-provisioning only) |

> [!TIP]
> The built-in **Editor** role (`roles/editor`) covers all of these. For least-privilege setups, use **Storage Object Creator** (`roles/storage.objectCreator`) plus **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`).

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

This affects auto-provisioned buckets only. For manually created buckets, set the location in the `gcloud storage buckets create` command.

### 6. Verify large file support

Test with a file over 20 MB:

```bash
agent-ear --auto --video ./large-presentation.mp4
```

You should see a GCS upload step in the output before the transcription begins.

## Auto-cleanup behaviour

Auto-provisioned buckets include a **7-day lifecycle delete rule**. This means:

- Staging files are automatically deleted 7 days after upload
- No manual cleanup needed
- Ongoing storage costs are minimal

Manually created buckets do **not** include this rule by default. Add it yourself if desired:

```bash
gcloud storage buckets update gs://YOUR_BUCKET \
  --lifecycle-file=<(echo '[{"action":{"type":"Delete"},"condition":{"age":7}}]')
```
