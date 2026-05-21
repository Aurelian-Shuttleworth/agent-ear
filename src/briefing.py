"""TTS briefing module — plays a spoken briefing before recording.

Implements a two-tier Director's Notes approach:
  Tier 1 (default): Inline prefix pattern from the Daily Smart Briefing
    "[speaking slowly] Speak warmly and at a relaxed, gentle pace. {text}"
  Tier 2 (opt-in):  Full Audio Profile + Director's Notes (Google TTS Guide)

Design informed by:
  - Daily Smart Briefing production HA script (Pyscript pipeline)
  - Google TTS Prompting Guide (ai.google.dev/gemini-api/docs/speech-generation)
  - Google Vertex AI TTS docs (docs.cloud.google.com/text-to-speech/docs/gemini-tts)
"""

import os
import subprocess
import sys
import tempfile
import wave

import yaml
from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

from config import (
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    TTS_CHANNELS,
    TTS_SAMPLE_WIDTH,
    TTS_SAMPLERATE,
)

logger = logging.getLogger(__name__)


def _is_transient_error(exc: BaseException) -> bool:
    """Check if an exception is a transient server error worth retrying."""
    err_str = str(exc)
    return any(
        code in err_str
        for code in ["500", "503", "INTERNAL", "UNAVAILABLE", "DEADLINE"]
    )


def parse_briefing_file(briefing_path: str) -> tuple[str, dict | None]:
    """Parse a briefing file with optional YAML frontmatter.

    Supports:
      ---
      style: calm, professional
      pace: slowly
      format: inline  # or "full"
      voice: Kore
      ---
      Here is the briefing text...

    Returns:
        tuple: (briefing_text, director_notes_dict_or_None)
    """
    with open(briefing_path) as f:
        content = f.read()

    # Check for YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                notes = yaml.safe_load(parts[1])
                text = parts[2].strip()
                return text, notes if isinstance(notes, dict) else None
            except yaml.YAMLError:
                # Malformed frontmatter — treat entire content as text
                pass

    return content.strip(), None


# Pace labels are preserved in frontmatter for human documentation
# but intentionally NOT passed to the TTS model. The Gemini TTS API
# interprets any pace instruction too literally, producing
# syllable-by-syllable speech even with soft wording like
# "at a calm, measured pace". Style alone carries natural pacing.


def build_tts_prompt(
    briefing_text: str, director_notes: dict | None = None
) -> str:
    """Build a TTS prompt for the Vertex AI generate_content API.

    Uses the official Google TTS pattern for Vertex AI:
      "{style prompt}: {text}"

    The colon separates the style instruction (not spoken) from the
    text content (spoken). Validated via round-trip diagnostic test.

    Note: The `pace` frontmatter key is intentionally NOT passed to
    the TTS model. Gemini interprets pace directives too literally.
    Style descriptions (e.g. "calm, professional") already imply
    appropriate pacing.

    See: docs.cloud.google.com/text-to-speech/docs/gemini-tts#use_vertex_ai_api

    Returns:
        Prompt string ready for generate_content contents.
    """
    notes = director_notes or {}
    style = notes.get("style", "warm and natural")

    # Build the style prompt (everything before the colon — never spoken)
    # Pace is intentionally excluded — the model reads it too literally.
    style_prompt = f"Say the following in a {style} tone"

    return f"{style_prompt}: {briefing_text}"


@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _generate_tts_audio(
    client: genai.Client,
    prompt: str,
    voice: str,
    language_code: str = "en-US",
) -> bytes:
    """Generate TTS audio via Vertex AI Gemini TTS.

    The prompt contains both director's notes and transcript in a
    structured format. The TTS model only speaks the TRANSCRIPT section.

    Returns:
        Raw PCM s16le audio bytes (24kHz mono).
    """
    config = types.GenerateContentConfig(
        speech_config=types.SpeechConfig(
            language_code=language_code,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voice,
                )
            ),
        ),
        response_modalities=["AUDIO"],
        temperature=2.0,
    )

    pcm_data = bytes()
    for chunk in client.models.generate_content_stream(
        model=DEFAULT_TTS_MODEL,
        contents=prompt,
        config=config,
    ):
        if (
            chunk.candidates
            and chunk.candidates[0].content
            and chunk.candidates[0].content.parts
        ):
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                pcm_data += part.inline_data.data

    return pcm_data


def play_briefing(
    client: genai.Client,
    briefing_text: str,
    voice: str = DEFAULT_TTS_VOICE,
    project_id: str | None = None,
    location: str = "global",
    director_notes: dict | None = None,
) -> bool:
    """Generate and play a TTS briefing.

    Uses the Vertex AI Gemini TTS API with streaming response.
    PCM s16le (24kHz mono) → WAV wrapping via Python wave module.

    Args:
        client: Configured google-genai Client.
        briefing_text: Text to speak.
        voice: Gemini voice name (default: Kore).
        project_id: GCP project (for logging).
        location: Gemini location.
        director_notes: Optional director notes dict.

    Returns:
        True if briefing played successfully, False on error.
    """
    # Resolve voice and language from director_notes
    notes = director_notes or {}
    voice = notes.get("voice", voice)
    language_code = notes.get("language_code", "en-US")

    prompt = build_tts_prompt(briefing_text, director_notes)
    print(f"🎙️  Generating TTS briefing (voice: {voice})...")

    try:
        pcm_data = _generate_tts_audio(client, prompt, voice, language_code)

        if not pcm_data or len(pcm_data) < 1024:
            print("⚠️  TTS returned insufficient audio data", file=sys.stderr)
            return False

        # PCM → WAV via Python wave module (same as Pyscript pipeline)
        wav_path = _pcm_to_wav(pcm_data)

        # Play audio
        _play_audio(wav_path)

        # Cleanup
        try:
            os.remove(wav_path)
        except OSError:
            pass

        return True

    except Exception as e:
        print(f"⚠️  TTS briefing failed: {e}", file=sys.stderr)
        return False


def _pcm_to_wav(pcm_data: bytes) -> str:
    """Wrap raw PCM s16le data in a WAV header.

    Same approach as the Daily Smart Briefing Pyscript pipeline:
    24kHz mono 16-bit signed PCM → WAV file.

    Returns:
        Path to temporary WAV file.
    """
    tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = tf.name
    tf.close()

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(TTS_CHANNELS)
        wf.setsampwidth(TTS_SAMPLE_WIDTH)
        wf.setframerate(TTS_SAMPLERATE)
        wf.writeframes(pcm_data)

    return wav_path


def _play_audio(wav_path: str):
    """Play a WAV file using platform-appropriate player.

    Plays a short silent "ping" first to pre-warm the audio subsystem,
    preventing the beginning of the actual audio from being cut off.
    """
    if sys.platform == "darwin":
        _prewarm_audio()
        print("🔊 Playing briefing...")
        subprocess.run(["afplay", wav_path], check=True)
    elif sys.platform == "linux":
        print("🔊 Playing briefing...")
        subprocess.run(["aplay", wav_path], check=True)
    else:
        print(f"⚠️  Unsupported platform for playback: {sys.platform}", file=sys.stderr)


def _prewarm_audio():
    """Play a very short silent WAV to wake up the macOS audio subsystem.

    macOS audio output devices can take ~100-200ms to initialize on first
    use, causing the beginning of real audio to be clipped. Playing a
    brief silence first ensures the connection is fully active.
    """
    import struct
    import time

    silence_path = os.path.join(tempfile.gettempdir(), "agent_ear_prewarm.wav")
    # Generate 200ms of silence at 24kHz 16-bit mono
    num_samples = int(0.2 * TTS_SAMPLERATE)
    silent_frames = struct.pack(f"<{num_samples}h", *([0] * num_samples))

    with wave.open(silence_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(TTS_SAMPLE_WIDTH)
        wf.setframerate(TTS_SAMPLERATE)
        wf.writeframes(silent_frames)

    try:
        subprocess.run(["afplay", silence_path], check=True)
        # Tiny pause to let the audio subsystem settle
        time.sleep(0.1)
    except subprocess.CalledProcessError:
        pass  # Non-critical — proceed with playback anyway
    finally:
        try:
            os.remove(silence_path)
        except OSError:
            pass
