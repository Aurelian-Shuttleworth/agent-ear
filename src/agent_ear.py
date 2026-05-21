"""Core agentic listening engine — orchestrates validate → brief → record → transcribe.

This is the heart of agent-ear. It coordinates:
1. Prompt validation (optional, LLM-as-a-judge)
2. TTS briefing (optional, Director's Notes)
3. Audio recording (sounddevice InputStream)
4. Constrained transcription (Gemini, system_instruction separation)

Design informed by:
  - transcribe_note.py (recording, upload, API patterns)
  - Gemini 3 best practices (system_instruction separation, XML tags)
  - Daily Smart Briefing (TTS pipeline)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import numpy as np
import sounddevice as sd
import soundfile as sf
from datetime import datetime
from google import genai
from google.genai import types
from google.api_core import exceptions as api_exceptions
from google.cloud import storage as gcs

from briefing import parse_briefing_file, play_briefing
from gcs_provisioning import ensure_gcs_ready
from config import (
    DEFAULT_LOCATION,
    DEFAULT_TRANSCRIPTION_MODEL,
    DEFAULT_VALIDATION_MODEL,
    DEFAULT_VIDEO_MODEL,
    INLINE_THRESHOLD,
    RECORDING_SAMPLERATE,
    create_client,
    resolve_config,
    resolve_gcs_bucket,
    resolve_output_dir,
)
from cost_tracker import CostTracker
from prompt_validator import (
    BriefingValidationResult,
    ValidationResult,
    validate_briefing,
    validate_prompt,
)


# YouTube URL detection
YOUTUBE_PATTERN = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+")

# MIME type mapping for video files
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}


class SleepPrevention:
    """Prevent macOS sleep during recording/transcription."""

    def __enter__(self):
        self._proc = None
        if sys.platform == "darwin":
            self._proc = subprocess.Popen(
                ["caffeinate", "-dimsu"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return self

    def __exit__(self, *args):
        if self._proc:
            self._proc.terminate()
            self._proc.wait()


def run_pipeline(
    prompt_file: str | None = None,
    prompt_text: str | None = None,
    briefing_file: str | None = None,
    input_file: str | None = None,
    video: str | None = None,
    output_dir: str | None = None,
    output_format: str = "markdown",
    model: str | None = None,
    project_id: str | None = None,
    location: str = DEFAULT_LOCATION,
    validate: bool = True,
    auto: bool = False,
    high_res: bool = False,
    gcs_bucket: str | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Run the full agentic listening pipeline.

    Returns:
        dict with keys: output_path, content, format, cost, validation_result
    """
    result = {
        "output_path": None,
        "content": None,
        "format": output_format,
        "cost": 0.0,
        "validation_result": None,
        "exit_code": 0,
    }

    # Global cost tracker — threads through all Gemini calls
    tracker = CostTracker()

    # --- 0. Config resolution ---
    resolved_project, resolved_location = resolve_config(project_id, location)

    # --- 0.5 Client initialization (Vertex AI → API key fallback) ---
    client, is_vertex = create_client(resolved_project, resolved_location)
    if client is None:
        print(
            "❌ No authentication configured.\n"
            "Either:\n"
            "  • Set GOOGLE_API_KEY for Google AI Studio\n"
            "  • Set GOOGLE_CLOUD_PROJECT + run: gcloud auth application-default login\n"
            "  • Run: gcloud config set project <PROJECT_ID>",
            file=sys.stderr,
        )
        result["exit_code"] = 1
        return result

    mode_label = f"Vertex AI (Project: {resolved_project})" if is_vertex else "Google AI Studio (API key)"
    print(f"🔑 Auth: {mode_label}")

    # --- 1. Load agent prompt ---
    agent_prompt = _load_prompt(prompt_file, prompt_text)

    # --- 2. Validate prompt (if provided and validation enabled) ---
    if agent_prompt and validate:
        print("🔍 Validating agent prompt...")
        vr, vr_response = validate_prompt(client, agent_prompt)
        result["validation_result"] = vr
        if vr_response:
            tracker.track(DEFAULT_VALIDATION_MODEL, vr_response)

        if not vr.valid:
            print(f"❌ Prompt validation failed (score: {vr.score}/5)")
            print(f"   Feedback: {vr.feedback}")
            if vr.improved_prompt:
                print(f"   Suggested improvement:\n{vr.improved_prompt}")
            result["exit_code"] = 2
            return result

        print(f"✅ Prompt validated (score: {vr.score}/5)")

    # --- 2.5 Validate briefing (if provided and validation enabled) ---
    briefing_text = None
    director_notes = None
    if briefing_file:
        briefing_text, director_notes = parse_briefing_file(briefing_file)

        if validate:
            print("🔍 Validating TTS briefing...")
            bvr, bvr_response = validate_briefing(client, briefing_text, director_notes)
            result["briefing_validation_result"] = bvr
            if bvr_response:
                tracker.track(DEFAULT_VALIDATION_MODEL, bvr_response)

            for w in bvr.warnings:
                print(f"   ⚠️  {w}")

            if not bvr.valid:
                print(f"⚠️  Briefing validation warning (score: {bvr.score}/5)")
                print(f"   {bvr.feedback}")

            # Auto-fix: apply suggested improvements
            if bvr.improved_text:
                print("   ✏️  Auto-fixing briefing text")
                briefing_text = bvr.improved_text
            if bvr.improved_notes:
                print(f"   ✏️  Auto-fixing director notes: {bvr.improved_notes}")
                director_notes = {**(director_notes or {}), **bvr.improved_notes}

            print(f"{'✅' if bvr.valid else '⚠️'} Briefing validated (score: {bvr.score}/5)")

    # --- 3. TTS briefing (if briefing text available) ---
    if briefing_text:
        success = play_briefing(
            client=client,
            briefing_text=briefing_text,
            director_notes=director_notes,
            project_id=resolved_project,
            location=resolved_location,
        )
        if not success:
            print("⚠️  TTS briefing failed, continuing to recording...", file=sys.stderr)

    # --- 4. Record or load audio ---
    is_video = bool(video)
    is_youtube = bool(video and YOUTUBE_PATTERN.match(video))
    is_fresh_recording = False  # Track whether we recorded new audio
    recovery_path = None  # Persistent copy of the recording

    with SleepPrevention():
        if video:
            media_path = _preprocess_video(video)
        elif input_file:
            media_path = input_file
        else:
            media_path = _record_audio()
            is_fresh_recording = True

            # --- 4.5 Safety copy: persist recording outside /tmp ---
            # macOS aggressively cleans /tmp — save to a durable location
            # immediately so the recording survives crashes.
            resolved_out = resolve_output_dir(output_dir)
            recovery_dir = os.path.join(resolved_out, ".recovery")
            os.makedirs(recovery_dir, exist_ok=True)
            safe_date_for_recovery = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            recovery_path = os.path.join(
                recovery_dir, f"recording_{safe_date_for_recovery}.wav"
            )
            shutil.copy2(media_path, recovery_path)
            print(f"🛡️  Recording backed up: {recovery_path}")

        # --- 5. Transcribe ---
        safe_date = datetime.now().strftime("%Y-%m-%d")
        model_name = model or (DEFAULT_VIDEO_MODEL if is_video else DEFAULT_TRANSCRIPTION_MODEL)

        try:
            content = _transcribe(
                client=client,
                media_path=media_path,
                project_id=resolved_project,
                is_vertex=is_vertex,
                model_name=model_name,
                agent_prompt=agent_prompt,
                safe_date=safe_date,
                is_video=is_video,
                is_youtube=is_youtube,
                high_res=high_res,
                gcs_bucket=gcs_bucket,
                output_format=output_format,
                tracker=tracker,
                auto=auto,
                max_tokens=max_tokens,
            )
        except Exception as e:
            # Recording is safe — tell the user where to find it
            if recovery_path and os.path.exists(recovery_path):
                print(
                    f"\n🛡️  Recording preserved at: {recovery_path}",
                    file=sys.stderr,
                )
                print(
                    f"   Re-run with: agent-ear --input-file '{recovery_path}' "
                    f"{'--prompt-file ' + prompt_file if prompt_file else ''} --auto",
                    file=sys.stderr,
                )
            raise

    # --- 5.5 Obsidian final pass (if raw output lacks frontmatter) ---
    if output_format == "markdown" and not content.strip().startswith("---"):
        print("📝 Adding Obsidian frontmatter via final pass...")
        content = _obsidian_final_pass(client, content, safe_date, tracker)

    result["content"] = content
    result["cost"] = tracker.total_cost_usd

    # --- 6. Save output ---
    output_dir = resolve_output_dir(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if output_format == "json":
        result["output_path"] = _save_json(content, output_dir, safe_date, auto)
    elif output_format == "raw":
        result["output_path"] = _save_raw(content, output_dir, safe_date, auto)
    else:
        result["output_path"] = _save_markdown(content, output_dir, safe_date, auto)

    # --- 7. Cost summary ---
    tracker.print_summary()

    # --- 8. Cleanup: only on FULL success ---
    # Remove temp recording from /tmp
    if is_fresh_recording and media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except OSError:
            pass
    # Remove recovery copy (output was saved successfully)
    if recovery_path and os.path.exists(recovery_path):
        try:
            os.remove(recovery_path)
            # Clean up .recovery dir if empty
            recovery_dir = os.path.dirname(recovery_path)
            if not os.listdir(recovery_dir):
                os.rmdir(recovery_dir)
        except OSError:
            pass

    return result


def _load_prompt(prompt_file: str | None, prompt_text: str | None) -> str | None:
    """Load agent prompt from file or inline text."""
    if prompt_file:
        with open(prompt_file) as f:
            return f.read().strip()
    if prompt_text:
        return prompt_text.strip()
    return None


def _record_audio() -> str:
    """Record audio from microphone until Ctrl+C or Stop button (macOS)."""
    tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output_path = tf.name
    tf.close()

    # Play readiness sound (macOS)
    if sys.platform == "darwin":
        try:
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"])
        except Exception:
            pass

    print("🎙️  Recording... Press Ctrl+C to stop.")
    q = []

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.append(indata.copy())

    # Launch macOS stop-button dialog
    btn_process = None
    if sys.platform == "darwin":
        try:
            script = (
                'display dialog "🎙️ Anti-Gravity Agent-Ear\\n\\n'
                'Click Stop to finish recording." '
                'buttons {"Stop"} default button "Stop" '
                'with icon note with title "Anti-Gravity"'
            )
            btn_process = subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"⚠️ Could not launch GUI button: {e}")

    try:
        with sd.InputStream(
            samplerate=RECORDING_SAMPLERATE, channels=1, callback=callback
        ):
            while True:
                # Check if Stop button was clicked
                if btn_process and btn_process.poll() is not None:
                    print("\n🛑 Stop button clicked.")
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Recording stopped.")
    finally:
        # Dismiss the dialog if still open
        if btn_process and btn_process.poll() is None:
            btn_process.terminate()

    recording = np.concatenate(q)
    print(f"💾 Saving recording ({len(recording) / RECORDING_SAMPLERATE:.1f}s)...")
    sf.write(output_path, recording, RECORDING_SAMPLERATE)
    return output_path


def _preprocess_video(video_path: str) -> str:
    """Download YouTube or preprocess local video."""
    if YOUTUBE_PATTERN.match(video_path):
        return _download_youtube(video_path)
    return video_path


def _download_youtube(url: str) -> str:
    """Download a YouTube video to a temporary file.

    Format selection optimised for Gemini multimodal analysis:
    - 720p max: Gemini samples video at 1 fps, so higher resolution is wasted
      bandwidth and risks exceeding the 20MB inline upload threshold.
    - MP4 container with merged audio: required for Gemini's audio+video analysis.
    - Falls back to best available MP4 if 720p isn't available.
    """
    print(f"⬇️  Downloading video from {url}...")
    tf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    temp_path = tf.name
    tf.close()

    try:
        cmd = [
            "yt-dlp",
            # Prefer ≤720p mp4 with audio; fall back to best mp4 with separate audio merge
            "-f", "best[height<=720][ext=mp4]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--force-overwrites",  # tempfile pre-creates a 0-byte file; must overwrite
            "-o", temp_path,
            url,
        ]
        subprocess.run(cmd, check=True)
        size_mb = os.path.getsize(temp_path) / (1024 * 1024)
        print(f"✅ Download complete: {temp_path} ({size_mb:.1f} MB)")
        if size_mb > 20:
            print(f"⚠️  File exceeds 20MB inline limit — will require GCS staging")
        return temp_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"Video download failed: {e}")


def _transcribe(
    client: genai.Client,
    media_path: str,
    project_id: str | None,
    is_vertex: bool,
    model_name: str,
    agent_prompt: str | None,
    safe_date: str,
    is_video: bool,
    is_youtube: bool,
    high_res: bool,
    gcs_bucket: str | None,
    output_format: str,
    tracker: CostTracker | None = None,
    auto: bool = False,
    max_tokens: int | None = None,
) -> str:
    """Transcribe media using Gemini with optional agent prompt constraints."""
    print(f"\n🧠 Using model: {model_name}")

    # Build content part — all media (including downloaded YouTube) goes through
    # _upload_media which handles inline (<20MB) or GCS staging (>20MB)
    mime_type = _detect_mime_type(media_path, is_video)
    part = _upload_media(
        client, media_path, mime_type, project_id, gcs_bucket, is_vertex,
        auto=auto,
    )

    # Build system prompt
    if agent_prompt:
        system_prompt = agent_prompt
    else:
        system_prompt = _build_default_system_prompt(safe_date, is_video)

    # Configure generation — dynamic token allocation based on media duration
    if max_tokens is None:
        if is_video:
            max_tokens = 32768  # Needs headroom for comprehensive structured extraction
        else:
            # Scale output tokens with recording duration to prevent truncation
            duration_s = _get_audio_duration(media_path)
            if duration_s and duration_s > 120:
                # ~50 tokens/minute of speech, with generous headroom for structure
                estimated = int(duration_s / 60 * 200)
                max_tokens = min(max(estimated, 8192), 65536)
                print(f"📏 Dynamic token budget: {max_tokens} (for {duration_s:.0f}s recording)")
            else:
                max_tokens = 8192
    config_kwargs = dict(
        system_instruction=system_prompt,
        temperature=0.2,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
    )
    if is_video and high_res:
        config_kwargs["media_resolution"] = types.MediaResolution.MEDIA_RESOLUTION_HIGH
        print("🔍 Using MEDIA_RESOLUTION_HIGH for text-heavy video")

    print(f"✨ Generating transcription with {model_name}...")

    response = _call_gemini(
        client, model_name, [part], types.GenerateContentConfig(**config_kwargs), "Transcription"
    )

    # Cost tracking via global tracker
    if tracker:
        tracker.track(model_name, response)

    return _validate_response(response)


def _build_default_system_prompt(safe_date: str, is_video: bool) -> str:
    """Build the default system prompt conforming to FR-PRF-5."""
    note_type = "video-note" if is_video else "audio-note"
    media_name = "video" if is_video else "audio recording"

    return f"""\
You are an expert Personal Knowledge Management Assistant extracting
structured content from {media_name} for an Obsidian vault.

STRATEGY:
1. Listen to the ENTIRE {media_name} before producing output.
2. {'Reference timestamps (MM:SS) for all key events and visual elements.' if is_video else 'Provide a complete verbatim transcription.'}
3. Prioritise DEPTH over brevity — capture every distinct point made.

OUTPUT FORMAT — produce a complete Obsidian Markdown note with ALL sections.

---
slug: concise-kebab-case-title
tags:
  - {note_type}
  - inbox
creation_date: {safe_date}
status: inbox
category: To Process
---

## Executive Summary
3-5 sentence comprehensive overview of the purpose and central thesis.

## Key Points / Action Items
Comprehensive bulleted list of all data points, tasks, and important takeaways.
{'Include timestamps (MM:SS) for each point.' if is_video else ''}

## {'Detailed Transcript Summary & Visuals' if is_video else 'Verbatim Transcript'}
{'A rich, timestamped (MM:SS) summary describing BOTH the spoken content and EVERY visual element shown on screen. Describe visuals following WCAG SC 1.2.3 standards so a blind user understands the visual content completely.' if is_video else 'A COMPLETE verbatim transcription — every word exactly as spoken, including filler words and natural speech patterns. Do NOT summarise or paraphrase.'}

GUIDELINES:
- Be comprehensive and exhaustive.
- {'Always use timestamps to ground details in the video timeline.' if is_video else 'Include all filler words (um, uh, ah) and self-corrections.'}

DO NOT:
- Produce a brief, shallow summary.
- Skip generating the YAML frontmatter.
- Skip sections even if sparse.

Output ONLY the markdown content, starting with `---`.
"""


OBSIDIAN_WRAP_PROMPT = """\
You are an Obsidian Note Formatter fixing the layout of raw text transcriptions.

STRATEGY:
1. Read the provided raw text completely.
2. Generatively create the appropriate YAML frontmatter fields (slug, tags).
3. Prepend the frontmatter to the raw text.

OUTPUT FORMAT:
---
slug: kebab-case-summary-of-the-content
tags: [3-5 relevant kebab-case tags, ALWAYS include #audio-note and #inbox]
creation_date: {date}
status: inbox
category: To Process
---
[EXACT ORIGINAL CONTENT]

GUIDELINES:
- Output MUST start with `---` (YAML frontmatter delimiter).
- Preserve the original content EXACTLY character-for-character.
- If the content lacks section headers, add a single "## Content" header.
- Provide NO pleasantries or surrounding text.

DO NOT:
- Alter, summarise, truncate, or hallucinate the main content body.
- Output anything other than the final formatted Markdown string."""


def _obsidian_final_pass(
    client: genai.Client,
    content: str,
    safe_date: str,
    tracker: CostTracker,
) -> str:
    """Wrap raw transcription output in Obsidian frontmatter.

    Uses flash-lite for minimal cost. Preserves content verbatim,
    only adding YAML frontmatter with slug, tags, creation_date, etc.
    """
    model = DEFAULT_VALIDATION_MODEL  # flash-lite — cheapest option

    try:
        response = client.models.generate_content(
            model=model,
            contents=f"<content>\n{content}\n</content>",
            config=types.GenerateContentConfig(
                system_instruction=OBSIDIAN_WRAP_PROMPT.format(date=safe_date),
                temperature=0.0,
            ),
        )
        tracker.track(model, response)
        wrapped = response.text.strip()

        # Validate output starts with frontmatter
        if wrapped.startswith("---"):
            print("✅ Obsidian frontmatter added")
            return wrapped
        else:
            print("⚠️  Final pass didn't produce frontmatter, using original content")
            return content

    except Exception as e:
        print(f"⚠️  Obsidian final pass failed: {e}", file=sys.stderr)
        return content


def _get_audio_duration(media_path: str) -> float | None:
    """Get audio file duration in seconds, or None if unavailable."""
    try:
        info = sf.info(media_path)
        return info.duration
    except Exception:
        return None


def _detect_mime_type(media_path: str, is_video: bool) -> str:
    """Detect MIME type from file extension."""
    if not is_video:
        return "audio/wav"
    ext = os.path.splitext(media_path)[1].lower()
    return VIDEO_MIME_TYPES.get(ext, "video/mp4")


def _upload_media(client, media_path, mime_type, project_id, bucket_name=None, is_vertex=True, auto=False):
    """Upload media via inline or GCS based on size.

    GCS upload requires Vertex AI mode (a GCP project). In API key mode,
    files exceeding the inline threshold will raise an error.

    If the GCS bucket doesn't exist, triggers interactive provisioning
    (unless auto=True, in which case it errors).
    """
    size = os.path.getsize(media_path)

    if size <= INLINE_THRESHOLD:
        print(f"📤 Inline upload ({size / (1024*1024):.1f} MB)")
        with open(media_path, "rb") as f:
            return types.Part.from_bytes(data=f.read(), mime_type=mime_type)
    else:
        if not is_vertex:
            raise RuntimeError(
                f"❌ File too large for inline upload ({size / (1024*1024):.1f} MB > "
                f"{INLINE_THRESHOLD / (1024*1024):.0f} MB).\n"
                "GCS staging requires a Google Cloud project (Vertex AI mode).\n"
                "Either reduce file size or set GOOGLE_CLOUD_PROJECT."
            )
        resolved_bucket = resolve_gcs_bucket(bucket_name, project_id)
        # Auto-provision: check API + bucket, create if needed
        resolved_bucket = ensure_gcs_ready(project_id, resolved_bucket, auto=auto)
        gcs_uri = _upload_to_gcs(media_path, resolved_bucket)
        print(f"✅ GCS upload complete → {gcs_uri}")
        return types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)


def _upload_to_gcs(local_path, bucket_name):
    """Upload a local file to GCS and return its gs:// URI."""
    try:
        client = gcs.Client()
    except Exception as e:
        raise RuntimeError(
            f"Could not initialise GCS client: {e}\n"
            "Run: gcloud auth application-default login"
        ) from e

    bucket = client.bucket(bucket_name)
    blob_name = f"staging/{uuid.uuid4().hex}/{os.path.basename(local_path)}"
    blob = bucket.blob(blob_name)

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"📤 GCS upload ({size_mb:.1f} MB) → gs://{bucket_name}/{blob_name}...")
    blob.upload_from_filename(local_path)
    return f"gs://{bucket_name}/{blob_name}"


def _call_gemini(client, model_name, contents, config, phase_label):
    """Call Gemini with retry logic on transient errors."""
    _TRANSIENT = (
        api_exceptions.ServiceUnavailable,
        api_exceptions.InternalServerError,
        api_exceptions.DeadlineExceeded,
        ConnectionError,
    )
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(
                model=model_name, contents=contents, config=config
            )
        except _TRANSIENT as e:
            if attempt < max_attempts:
                delay = 2 * attempt
                print(
                    f"⚠️  {phase_label}: transient error ({type(e).__name__}), "
                    f"retrying in {delay}s ({attempt}/3)...",
                    file=sys.stderr,
                )
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"❌ {phase_label}: Gemini unavailable after 3 retries."
                )
        except api_exceptions.ResourceExhausted:
            raise RuntimeError(
                f"❌ {phase_label}: Gemini quota exhausted. "
                "Wait a few minutes or check console.cloud.google.com."
            )
        except api_exceptions.Unauthenticated:
            raise RuntimeError(
                f"❌ {phase_label}: Authentication failed. "
                "Run: gcloud auth application-default login"
            )
        except api_exceptions.PermissionDenied:
            raise RuntimeError(
                f"❌ {phase_label}: Permission denied. "
                "Ensure Vertex AI API is enabled."
            )
        except Exception:
            raise


def _validate_response(response):
    """Validate finish_reason and extract text."""
    candidate = response.candidates[0]
    reason = candidate.finish_reason
    if reason == "STOP":
        return response.text
    if reason == "MAX_TOKENS":
        print("⚠️ Response truncated (MAX_TOKENS) — output may be incomplete")
        return response.text
    if reason == "SAFETY":
        raise RuntimeError("Response blocked by safety filter")
    if reason == "RECITATION":
        raise RuntimeError("Response blocked due to potential recitation")
    raise RuntimeError(f"Unexpected finish_reason: {reason}")


def _save_markdown(content: str, output_dir: str, safe_date: str, auto: bool) -> str:
    """Save transcription as Obsidian markdown note."""
    # Extract slug from frontmatter
    slug = _extract_slug(content, "untitled")

    if not auto:
        try:
            topic = input("\n📝 Topic (press Enter for auto): ").strip()
            if topic:
                slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
        except (EOFError, KeyboardInterrupt):
            pass

    # Count existing notes for numbering
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_{slug}.md"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w") as f:
        f.write(content)
    print(f"\n✅ Note saved: {output_path}")
    return output_path


def _save_json(content: str, output_dir: str, safe_date: str, auto: bool) -> str:
    """Save transcription as structured JSON."""
    slug = _extract_slug(content, "untitled")
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_{slug}.json"
    output_path = os.path.join(output_dir, filename)

    data = {
        "date": safe_date,
        "slug": slug,
        "format": "json",
        "content": content,
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON saved: {output_path}")
    return output_path


def _save_raw(content: str, output_dir: str, safe_date: str, auto: bool) -> str:
    """Save raw transcript text."""
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_transcript.txt"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w") as f:
        f.write(content)
    print(f"\n✅ Transcript saved: {output_path}")
    return output_path


def _extract_slug(content: str, default: str = "untitled") -> str:
    """Extract slug from YAML frontmatter if present."""
    match = re.search(r"^slug:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return default
