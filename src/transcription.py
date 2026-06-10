"""Transcription module — Gemini API calls, retry logic, and response validation.

Handles:
  - Building default system prompts (audio vs video)
  - Dynamic token budget allocation based on recording duration
  - Gemini API calls with transient error retry (3 attempts)
  - Response validation (finish_reason handling)
  - Audio duration detection via soundfile
"""

import os
import sys
import time

import soundfile as sf
from google import genai
from google.api_core import exceptions as api_exceptions
from google.genai import types

from config import SAFETY_SETTINGS, model_supports_high_res_video
from cost_tracker import CostTracker
from upload import detect_mime_type, upload_media

# Thinking level hierarchy for promotion comparisons
_THINKING_LEVELS = ("minimal", "low", "medium", "high")


def resolve_thinking_config(
    model_name: str,
    duration_s: float | None,
    is_video: bool,
    high_res: bool,
    validator_hint: str | None = None,
    explicit_level: str | None = None,
) -> types.ThinkingConfig | None:
    """Resolve thinking configuration for a Gemini transcription call.

    Resolution priority:
      1. explicit_level (CLI --thinking-level or $AGENT_EAR_THINKING_LEVEL)
      2. validator_hint (from prompt validator LLM output)
      3. Duration-based default (fallback)

    Args:
        model_name: Gemini model name string.
        duration_s: Audio duration in seconds, or None if unknown.
        is_video: Whether the media is video.
        high_res: Whether MEDIA_RESOLUTION_HIGH is active.
        validator_hint: Optional thinking_level from the prompt validator.
        explicit_level: Optional CLI override.

    Returns:
        ThinkingConfig for the model family, or None if unsupported.
    """
    # Resolve the env var fallback for explicit level
    env_level = os.environ.get("AGENT_EAR_THINKING_LEVEL", "").lower().strip()
    effective_explicit = explicit_level or (env_level if env_level else None)

    # Priority 1: explicit override → Priority 2: validator hint → Priority 3: duration
    if effective_explicit and effective_explicit in _THINKING_LEVELS:
        resolved = effective_explicit
    elif validator_hint and validator_hint in _THINKING_LEVELS:
        resolved = validator_hint
    else:
        # Duration-based fallback
        if duration_s is None:
            resolved = "medium"
        elif duration_s <= 120:
            resolved = "low"
        elif duration_s <= 600:
            resolved = "medium"
        else:
            resolved = "high"

    # Promote to "high" for text-heavy video content
    if is_video and high_res:
        if _THINKING_LEVELS.index(resolved) < _THINKING_LEVELS.index("high"):
            resolved = "high"

    # Build model-compatible config
    if "gemini-3.5" in model_name:
        print(f"🧠 Thinking: level='{resolved}' (Gemini 3.5)")
        return types.ThinkingConfig(thinking_level=resolved)
    elif "gemini-3.1" in model_name or "gemini-2.5" in model_name:
        budget_map = {"minimal": 512, "low": 1024, "medium": 2048, "high": 4096}
        budget = budget_map.get(resolved, 2048)
        print(f"🧠 Thinking: budget={budget} (legacy, mapped from '{resolved}')")
        return types.ThinkingConfig(thinking_budget=budget)
    else:
        print("🧠 Thinking: not supported by this model")
        return None


def transcribe(
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
    non_interactive: bool = False,
    max_tokens: int | None = None,
    thinking_level: str | None = None,
    extra_tokens: int = 0,
) -> str:
    """Transcribe media using Gemini with optional agent prompt constraints.

    Args:
        client: Configured google-genai Client.
        media_path: Path to audio/video file.
        project_id: GCP project ID (for GCS uploads).
        is_vertex: Whether Vertex AI mode is active.
        model_name: Gemini model to use.
        agent_prompt: Optional system prompt for constrained transcription.
        safe_date: Date string for default prompt.
        is_video: Whether the media is video.
        is_youtube: Whether the source was a YouTube URL.
        high_res: Whether to use MEDIA_RESOLUTION_HIGH.
        gcs_bucket: Optional explicit GCS bucket name.
        output_format: Output format (markdown/json/raw).
        tracker: Optional CostTracker for usage tracking.
        non_interactive: Whether running in non-interactive mode.
        max_tokens: Optional max output tokens override.
        thinking_level: Optional explicit thinking level override.
        extra_tokens: Additive token budget from validator (0-16384).

    Returns:
        Transcription text content.
    """
    print(f"\n🧠 Using model: {model_name}")

    # Build content part — all media goes through upload_media
    # which handles inline (<100MB), Files API, or GCS staging
    mime_type = detect_mime_type(media_path, is_video)
    part = upload_media(
        client,
        media_path,
        mime_type,
        project_id,
        gcs_bucket,
        is_vertex,
        non_interactive=non_interactive,
    )

    # Build system prompt
    if agent_prompt:
        system_prompt = agent_prompt
    else:
        system_prompt = build_default_system_prompt(safe_date, is_video)

    # Configure generation — dynamic token allocation based on media duration
    duration_s = None
    if max_tokens is None:
        if is_video:
            max_tokens = 32768  # Needs headroom for comprehensive structured extraction
        else:
            # Scale output tokens with recording duration to prevent truncation
            duration_s = get_audio_duration(media_path)
            if duration_s and duration_s > 120:
                # ~50 tokens/minute of speech, with generous headroom for structure
                estimated = int(duration_s / 60 * 200)
                max_tokens = min(max(estimated, 8192), 65536)
                print(f"📏 Dynamic token budget: {max_tokens} (for {duration_s:.0f}s recording)")
            else:
                max_tokens = 8192
    else:
        # Even when max_tokens is provided, get duration for thinking resolution
        if not is_video:
            duration_s = get_audio_duration(media_path)

    # Apply validator's extra_tokens adjustment
    if extra_tokens > 0:
        max_tokens = min(max_tokens + extra_tokens, 65536)
        print(f"📏 Validator extra tokens: +{extra_tokens} → {max_tokens} total")

    config_kwargs = dict(
        system_instruction=system_prompt,
        temperature=0.2,
        max_output_tokens=max_tokens,
        safety_settings=SAFETY_SETTINGS,
    )

    # Resolve thinking configuration via priority chain
    thinking_config = resolve_thinking_config(
        model_name=model_name,
        duration_s=duration_s,
        is_video=is_video,
        high_res=high_res,
        validator_hint=thinking_level,  # validator hint or CLI override
        explicit_level=thinking_level,
    )
    if thinking_config is not None:
        config_kwargs["thinking_config"] = thinking_config

    if is_video and high_res:
        if model_supports_high_res_video(model_name):
            config_kwargs["media_resolution"] = types.MediaResolution.MEDIA_RESOLUTION_HIGH
            print("🔍 Using MEDIA_RESOLUTION_HIGH for text-heavy video")
        else:
            print(f"⚠️  --high-res requested but {model_name} does not support HIGH video resolution")
            print("   Auto-downgrading to standard resolution (only gemini-3.5+ supports HIGH for video)")

    print(f"✨ Generating transcription with {model_name}...")

    response = call_gemini(
        client,
        model_name,
        [part],
        types.GenerateContentConfig(**config_kwargs),
        "Transcription",
    )

    # Cost tracking via global tracker
    if tracker:
        tracker.track(model_name, response)

    return validate_response(response)


def build_default_system_prompt(safe_date: str, is_video: bool) -> str:
    """Build the default system prompt conforming to FR-PRF-5.

    Args:
        safe_date: Date string for frontmatter.
        is_video: Whether to generate video-specific or audio-specific prompt.

    Returns:
        System prompt string.
    """
    note_type = "video-note" if is_video else "audio-note"
    media_name = "video" if is_video else "audio recording"

    return f"""\
You are an expert Personal Knowledge Management Assistant extracting
structured content from {media_name} for an Obsidian vault.

STRATEGY:
1. Listen to the ENTIRE {media_name} before producing output.
2. {"Reference timestamps (MM:SS) for all key events and visual elements." if is_video else "Provide a complete verbatim transcription."}
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
{"Include timestamps (MM:SS) for each point." if is_video else ""}

## {"Detailed Transcript Summary & Visuals" if is_video else "Verbatim Transcript"}
{"A rich, timestamped (MM:SS) summary describing BOTH the spoken content and EVERY visual element shown on screen. Describe visuals following WCAG SC 1.2.3 standards so a blind user understands the visual content completely." if is_video else "A COMPLETE verbatim transcription — every word exactly as spoken, including filler words and natural speech patterns. Do NOT summarise or paraphrase."}

GUIDELINES:
- Be comprehensive and exhaustive.
- {"Always use timestamps to ground details in the video timeline." if is_video else "Include all filler words (um, uh, ah) and self-corrections."}

DO NOT:
- Produce a brief, shallow summary.
- Skip generating the YAML frontmatter.
- Skip sections even if sparse.

Output ONLY the markdown content, starting with `---`.
"""


def get_audio_duration(media_path: str) -> float | None:
    """Get audio file duration in seconds, or None if unavailable.

    Args:
        media_path: Path to the audio file.

    Returns:
        Duration in seconds, or None if the file format is unsupported.
    """
    try:
        info = sf.info(media_path)
        return info.duration
    except Exception:
        return None


def call_gemini(client, model_name, contents, config, phase_label):
    """Call Gemini with retry logic on transient errors.

    Retries up to 3 times on transient errors (503, 500, deadline exceeded).
    Fails immediately on quota, auth, and permission errors.

    Args:
        client: Configured google-genai Client.
        model_name: Gemini model name.
        contents: Content parts for the request.
        config: GenerateContentConfig.
        phase_label: Human-readable label for error messages.

    Returns:
        Gemini GenerateContentResponse.

    Raises:
        RuntimeError: On unrecoverable or exhausted-retry errors.
    """
    _TRANSIENT = (
        api_exceptions.ServiceUnavailable,
        api_exceptions.InternalServerError,
        api_exceptions.DeadlineExceeded,
        ConnectionError,
    )
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(model=model_name, contents=contents, config=config)
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
                raise RuntimeError(f"❌ {phase_label}: Gemini unavailable after 3 retries.")
        except api_exceptions.ResourceExhausted:
            raise RuntimeError(
                f"❌ {phase_label}: Gemini quota exhausted. "
                "Wait a few minutes or check console.cloud.google.com."
            )
        except api_exceptions.Unauthenticated:
            raise RuntimeError(
                f"❌ {phase_label}: Authentication failed. Run: gcloud auth application-default login"
            )
        except api_exceptions.PermissionDenied:
            raise RuntimeError(f"❌ {phase_label}: Permission denied. Ensure Vertex AI API is enabled.")
        except Exception:
            raise


def validate_response(response):
    """Validate finish_reason and extract text.

    Args:
        response: Gemini GenerateContentResponse.

    Returns:
        Extracted text content.

    Raises:
        RuntimeError: On SAFETY, RECITATION, unexpected finish reasons,
                      or empty response.
    """
    candidate = response.candidates[0]
    reason = candidate.finish_reason
    if reason == "STOP":
        text = response.text
        if text is None:
            raise RuntimeError("Model returned empty response (no text content)")
        return text
    if reason == "MAX_TOKENS":
        print("⚠️ Response truncated (MAX_TOKENS) — output may be incomplete")
        # response.text may be None when truncated; extract from parts directly
        text = response.text
        if text is None:
            parts = getattr(getattr(candidate, "content", None), "parts", None)
            if parts:
                text = "".join(part.text for part in parts if hasattr(part, "text"))
        if not text:
            raise RuntimeError(
                "Response truncated (MAX_TOKENS) and no text could be extracted.\n"
                "Try increasing --max-tokens or reducing input length."
            )
        return text
    if reason == "SAFETY":
        raise RuntimeError("Response blocked by safety filter")
    if reason == "RECITATION":
        raise RuntimeError("Response blocked due to potential recitation")
    raise RuntimeError(f"Unexpected finish_reason: {reason}")
