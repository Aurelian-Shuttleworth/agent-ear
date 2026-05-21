"""Shared configuration resolution for agent-ear.

Extracts the config resolution chain from transcribe_note.py and speak.py,
eliminating duplication. Follows the 4-tier priority: CLI → env → gcloud → default.
"""

import os
import subprocess

from google import genai

# Model constants — verified against Google model catalog 2026-03-19
DEFAULT_TRANSCRIPTION_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_VIDEO_MODEL = "gemini-3-flash-preview"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-tts"
DEFAULT_VALIDATION_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_LOCATION = "global"


def resolve_output_dir(cli_output_dir=None):
    """Resolve output directory via 3-tier chain: CLI → env → cwd."""
    return (
        cli_output_dir
        or os.environ.get("AGENT_EAR_OUTPUT_DIR")
        or os.getcwd()
    )

# Upload thresholds
INLINE_THRESHOLD = 20 * 1024 * 1024  # 20MB — inline vs GCS

# Audio constants
RECORDING_SAMPLERATE = 44100  # Standard quality for voice recording
TTS_SAMPLERATE = 24000  # Gemini TTS output rate (24kHz mono PCM)
TTS_CHANNELS = 1
TTS_SAMPLE_WIDTH = 2  # 16-bit signed PCM

# Default TTS voice
DEFAULT_TTS_VOICE = "Kore"  # Proven in Daily Smart Briefing production


def resolve_config(cli_project=None, cli_location=None):
    """Resolve project and location via 4-tier chain: CLI → env → gcloud → default.

    Returns:
        tuple: (project_id, location)
    """
    project = (
        cli_project
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or _gcloud_config("project")
        or None
    )
    location = (
        (cli_location if cli_location and cli_location != DEFAULT_LOCATION else None)
        or os.environ.get("GOOGLE_CLOUD_LOCATION")
        or _gcloud_config("compute/region")
        or DEFAULT_LOCATION
    )
    return project, location


def resolve_gcs_bucket(explicit_bucket=None, project_id=None):
    """Resolve GCS bucket for large file uploads.

    Priority: explicit → env → derived from project.
    """
    return (
        explicit_bucket
        or os.environ.get("AGENT_EAR_GCS_BUCKET")
        or (f"{project_id}-transcribe-staging" if project_id else None)
    )


def _gcloud_config(key):
    """Read a value from gcloud config, return None on failure."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", key],
            capture_output=True,
            text=True,
            check=True,
        )
        val = result.stdout.strip()
        return val if val and val != "(unset)" else None
    except Exception:
        return None


def create_client(project_id=None, location=None):
    """Create a google-genai Client with appropriate auth backend.

    Resolution order:
      1. Vertex AI — if project_id is available (uses ADC or GOOGLE_APPLICATION_CREDENTIALS)
      2. Google AI Studio — if GOOGLE_API_KEY env var is set
      3. None — caller should handle the error

    Returns:
        tuple: (genai.Client, bool) — client and whether Vertex AI mode is active.
               Vertex mode enables GCS uploads and project-scoped features.
    """
    if project_id:
        return genai.Client(
            vertexai=True,
            project=project_id,
            location=location or DEFAULT_LOCATION,
        ), True

    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key), False

    return None, False

