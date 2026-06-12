"""Media upload module — inline, Gemini Files API, and GCS upload routing.

Handles:
  - MIME type detection from file extension
  - Inline upload for files ≤100MB (Part.from_bytes)
  - Gemini Files API for AI Studio large files ≤2GB (client.files.upload)
  - GCS upload for Vertex AI or explicit --gcs-bucket (Part.from_uri)
"""

import os
import time
import uuid

from google.cloud import storage as gcs
from google.genai import types

from config import (
    FILES_API_POLL_INTERVAL,
    FILES_API_POLL_TIMEOUT,
    FILES_API_THRESHOLD,
    INLINE_THRESHOLD,
    resolve_gcs_bucket,
)

# MIME type mappings
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}

AUDIO_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".webm": "audio/webm",
}


def detect_mime_type(media_path: str, is_video: bool) -> str:
    """Detect MIME type from file extension.

    Args:
        media_path: Path to the media file.
        is_video: Whether this is a video file.

    Returns:
        MIME type string (e.g., "audio/wav", "video/mp4").
    """
    ext = os.path.splitext(media_path)[1].lower()
    if not is_video:
        return AUDIO_MIME_TYPES.get(ext, "audio/wav")
    return VIDEO_MIME_TYPES.get(ext, "video/mp4")


def upload_media(
    client,
    media_path,
    mime_type,
    project_id,
    bucket_name=None,
    is_vertex=True,
    non_interactive=False,
):
    """Upload media via inline, Gemini Files API, or GCS based on context.

    Upload strategy:
      - --gcs-bucket provided → GCS upload (any auth, any size)
      - Otherwise, fully automatic:
        - ≤ 100 MB → Inline (fastest)
        - > 100 MB + Vertex AI → GCS (auto-derived bucket)
        - > 100 MB + AI Studio → Gemini Files API (up to 2 GB)

    Args:
        client: Google GenAI client.
        media_path: Path to the local media file.
        mime_type: MIME type string.
        project_id: GCP project ID (for GCS bucket resolution).
        bucket_name: Explicit GCS bucket name (optional).
        is_vertex: Whether Vertex AI mode is active.
        non_interactive: If True, skip interactive prompts (retained for CLI compat).

    Returns:
        A types.Part or File object suitable for Gemini API content.
    """
    size = os.path.getsize(media_path)
    size_mb = size / (1024 * 1024)

    # ── Rule 1: Explicit --gcs-bucket → GCS. Always. ──
    has_explicit_gcs = bool(bucket_name or os.environ.get("AGENT_EAR_GCS_BUCKET"))
    if has_explicit_gcs:
        return _upload_gcs(media_path, mime_type, bucket_name, project_id)

    # ── Rule 2: Auto mode ──

    # Small files → inline (fastest, zero overhead)
    if size <= INLINE_THRESHOLD:
        print(f"📤 Inline upload ({size_mb:.1f} MB)")
        with open(media_path, "rb") as f:
            return types.Part.from_bytes(data=f.read(), mime_type=mime_type)

    # Large files → route by auth backend
    if is_vertex:
        return _upload_gcs(media_path, mime_type, bucket_name, project_id)

    # AI Studio → Gemini Files API (up to 2 GB)
    if size > FILES_API_THRESHOLD:
        raise RuntimeError(
            f"❌ File too large for Gemini Files API ({size_mb:.1f} MB > 2048 MB).\n"
            "Provide --gcs-bucket to stage via Google Cloud Storage."
        )
    return _upload_via_files_api(client, media_path, mime_type)


def _upload_gcs(media_path, mime_type, bucket_name, project_id):
    """Upload via GCS — expects an existing bucket.

    No auto-provisioning. If the bucket doesn't exist, the GCS client
    raises NotFound with a clear error.

    Args:
        media_path: Path to the local media file.
        mime_type: MIME type string.
        bucket_name: Explicit bucket name (may be None if derived).
        project_id: GCP project ID (for bucket name derivation).

    Returns:
        A types.Part with the GCS URI.
    """
    resolved_bucket = resolve_gcs_bucket(bucket_name, project_id)
    if not resolved_bucket:
        raise RuntimeError("❌ No GCS bucket configured.\nSet --gcs-bucket or $AGENT_EAR_GCS_BUCKET.")
    gcs_uri = _upload_to_gcs(media_path, resolved_bucket)
    print(f"✅ GCS upload complete → {gcs_uri}")
    return types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)


def _upload_via_files_api(client, media_path, mime_type):
    """Upload via Gemini Files API (AI Studio mode, files > 100 MB ≤ 2 GB).

    The Files API stores files on Google servers for 48 hours at no cost.
    Server-side processing is asynchronous — we poll until ACTIVE.

    Args:
        client: Google GenAI client (must be AI Studio / API key mode).
        media_path: Path to the local media file.
        mime_type: MIME type string (used by the Files API for processing).

    Returns:
        The File object (passable directly to generate_content contents).
    """
    size_mb = os.path.getsize(media_path) / (1024 * 1024)
    print(f"📤 Uploading via Gemini Files API ({size_mb:.1f} MB)...")

    uploaded_file = client.files.upload(file=media_path)
    print(f"⏳ Processing on Google servers ({uploaded_file.name})...")

    elapsed = 0
    while uploaded_file.state.name == "PROCESSING":
        if elapsed >= FILES_API_POLL_TIMEOUT:
            raise RuntimeError(
                f"❌ File processing timed out after {FILES_API_POLL_TIMEOUT}s.\n"
                f"File name: {uploaded_file.name}\n"
                "The file may still be processing — retry with --input-file."
            )
        time.sleep(FILES_API_POLL_INTERVAL)
        elapsed += FILES_API_POLL_INTERVAL
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise RuntimeError(
            f"❌ File processing failed on Google servers.\n"
            f"File: {uploaded_file.name}\n"
            "Try reducing file size or switching to Vertex AI + GCS."
        )

    print(f"✅ File ready: {uploaded_file.name} (expires in 48h)")
    return uploaded_file


def _upload_to_gcs(local_path, bucket_name):
    """Upload a local file to GCS and return its gs:// URI.

    Args:
        local_path: Path to the local file.
        bucket_name: GCS bucket name.

    Returns:
        GCS URI string (gs://bucket/path).
    """
    try:
        client = gcs.Client()
    except Exception as e:
        raise RuntimeError(
            f"Could not initialise GCS client: {e}\nRun: gcloud auth application-default login"
        ) from e

    bucket = client.bucket(bucket_name)
    blob_name = f"staging/{uuid.uuid4().hex}/{os.path.basename(local_path)}"
    blob = bucket.blob(blob_name)

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"📤 GCS upload ({size_mb:.1f} MB) → gs://{bucket_name}/{blob_name}...")
    blob.upload_from_filename(local_path)
    return f"gs://{bucket_name}/{blob_name}"
