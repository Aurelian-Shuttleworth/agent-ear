"""Tests for transcription.py — system prompts, retry logic, response validation."""

from unittest.mock import patch

import pytest
from google.api_core import exceptions as api_exceptions

from transcription import (
    build_default_system_prompt,
    call_gemini,
    resolve_thinking_config,
    validate_response,
)
from video import YOUTUBE_PATTERN


class TestBuildDefaultSystemPrompt:
    """Tests for default system prompt generation."""

    def test_audio_prompt_contains_audio_tag(self):
        """Audio prompt includes audio-note tag."""
        prompt = build_default_system_prompt("2026-05-23", is_video=False)
        assert "audio-note" in prompt, "Audio prompt should contain audio-note tag"

    def test_video_prompt_contains_video_tag(self):
        """Video prompt includes video-note tag."""
        prompt = build_default_system_prompt("2026-05-23", is_video=True)
        assert "video-note" in prompt, "Video prompt should contain video-note tag"

    def test_audio_prompt_requests_verbatim(self):
        """Audio prompt requests verbatim transcription."""
        prompt = build_default_system_prompt("2026-05-23", is_video=False)
        assert "verbatim" in prompt.lower(), (
            "Audio prompt should request verbatim transcription"
        )

    def test_video_prompt_requests_timestamps(self):
        """Video prompt requests timestamps."""
        prompt = build_default_system_prompt("2026-05-23", is_video=True)
        assert "timestamp" in prompt.lower(), "Video prompt should request timestamps"


class TestYouTubePattern:
    """Tests for YouTube URL regex matching."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtube.com/watch?v=abc123",
            "http://www.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
        ],
    )
    def test_matches_youtube_urls(self, url):
        """Regex matches valid YouTube URLs."""
        assert YOUTUBE_PATTERN.match(url), f"Should match YouTube URL: {url}"

    @pytest.mark.parametrize(
        "url",
        [
            "https://vimeo.com/123456",
            "https://example.com/video",
            "not-a-url",
        ],
    )
    def test_rejects_non_youtube(self, url):
        """Regex rejects non-YouTube URLs."""
        assert not YOUTUBE_PATTERN.match(url), f"Should reject: {url}"


class TestValidateResponse:
    """Tests for Gemini response finish_reason handling."""

    def test_stop_returns_text(self, mock_response):
        """STOP finish reason returns text normally."""
        response = mock_response(text="Hello world", finish_reason="STOP")
        result = validate_response(response)
        assert result == "Hello world", f"Should return text, got '{result}'"

    def test_max_tokens_returns_text(self, mock_response):
        """MAX_TOKENS returns text with warning (doesn't raise)."""
        response = mock_response(text="Truncated...", finish_reason="MAX_TOKENS")
        result = validate_response(response)
        assert result == "Truncated...", "Should return text even on MAX_TOKENS"

    def test_safety_raises(self, mock_response):
        """SAFETY finish reason raises RuntimeError."""
        response = mock_response(finish_reason="SAFETY")
        with pytest.raises(RuntimeError, match="safety filter"):
            validate_response(response)

    def test_recitation_raises(self, mock_response):
        """RECITATION finish reason raises RuntimeError."""
        response = mock_response(finish_reason="RECITATION")
        with pytest.raises(RuntimeError, match="recitation"):
            validate_response(response)

    def test_unexpected_reason_raises(self, mock_response):
        """Unknown finish reason raises RuntimeError."""
        response = mock_response(finish_reason="UNKNOWN_REASON")
        with pytest.raises(RuntimeError, match="Unexpected finish_reason"):
            validate_response(response)


class TestCallGemini:
    """Tests for Gemini API call retry logic."""

    def test_succeeds_first_attempt(self, mock_genai_client, mock_response):
        """No retry needed on success."""
        mock_genai_client.models.generate_content.return_value = mock_response()
        result = call_gemini(mock_genai_client, "model", ["content"], {}, "Test")
        assert result is not None, "Should return response on success"
        assert mock_genai_client.models.generate_content.call_count == 1

    @patch("transcription.time.sleep")
    def test_retries_on_transient(self, mock_sleep, mock_genai_client, mock_response):
        """Retries on ServiceUnavailable, succeeds on 3rd attempt."""
        mock_genai_client.models.generate_content.side_effect = [
            api_exceptions.ServiceUnavailable("503"),
            api_exceptions.ServiceUnavailable("503"),
            mock_response(),
        ]
        result = call_gemini(mock_genai_client, "model", ["content"], {}, "Test")
        assert result is not None, "Should succeed on 3rd attempt"
        assert mock_genai_client.models.generate_content.call_count == 3

    @patch("transcription.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep, mock_genai_client):
        """Raises RuntimeError after 3 transient failures."""
        mock_genai_client.models.generate_content.side_effect = (
            api_exceptions.ServiceUnavailable("503")
        )
        with pytest.raises(RuntimeError, match="unavailable after 3 retries"):
            call_gemini(mock_genai_client, "model", ["content"], {}, "Test")

    def test_no_retry_on_quota(self, mock_genai_client):
        """ResourceExhausted raises immediately without retry."""
        mock_genai_client.models.generate_content.side_effect = (
            api_exceptions.ResourceExhausted("429")
        )
        with pytest.raises(RuntimeError, match="quota exhausted"):
            call_gemini(mock_genai_client, "model", ["content"], {}, "Test")
        assert mock_genai_client.models.generate_content.call_count == 1

    def test_no_retry_on_auth_failure(self, mock_genai_client):
        """Unauthenticated raises immediately without retry."""
        mock_genai_client.models.generate_content.side_effect = (
            api_exceptions.Unauthenticated("401")
        )
        with pytest.raises(RuntimeError, match="Authentication failed"):
            call_gemini(mock_genai_client, "model", ["content"], {}, "Test")
        assert mock_genai_client.models.generate_content.call_count == 1

    def test_no_retry_on_permission_denied(self, mock_genai_client):
        """PermissionDenied raises immediately without retry."""
        mock_genai_client.models.generate_content.side_effect = (
            api_exceptions.PermissionDenied("403")
        )
        with pytest.raises(RuntimeError, match="Permission denied"):
            call_gemini(mock_genai_client, "model", ["content"], {}, "Test")
        assert mock_genai_client.models.generate_content.call_count == 1


class TestResolveThinkingConfig:
    """Tests for resolve_thinking_config() priority chain and model mapping."""

    def test_explicit_level_overrides_all(self):
        """CLI --thinking-level takes absolute priority."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=30,  # Would be "low" by duration
            is_video=False,
            high_res=False,
            validator_hint="medium",  # Would be "medium" by validator
            explicit_level="high",  # CLI override
        )
        assert config.thinking_level == "high", (
            f"Explicit level should win, got {config.thinking_level}"
        )

    def test_validator_hint_overrides_duration(self):
        """Validator hint beats duration-based default."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=30,  # Would be "low" by duration
            is_video=False,
            high_res=False,
            validator_hint="high",
        )
        assert config.thinking_level == "high", (
            f"Validator hint should override duration, got {config.thinking_level}"
        )

    def test_duration_fallback_short(self):
        """Short recordings (≤120s) resolve to 'low'."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=60,
            is_video=False,
            high_res=False,
        )
        assert config.thinking_level == "low", (
            f"Short recording should be 'low', got {config.thinking_level}"
        )

    def test_duration_fallback_medium(self):
        """Medium recordings (120-600s) resolve to 'medium'."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=300,
            is_video=False,
            high_res=False,
        )
        assert config.thinking_level == "medium", (
            f"Medium recording should be 'medium', got {config.thinking_level}"
        )

    def test_duration_fallback_long(self):
        """Long recordings (>600s) resolve to 'high'."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=900,
            is_video=False,
            high_res=False,
        )
        assert config.thinking_level == "high", (
            f"Long recording should be 'high', got {config.thinking_level}"
        )

    def test_none_duration_defaults_to_medium(self):
        """Unknown duration (None) defaults to 'medium'."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=None,
            is_video=False,
            high_res=False,
        )
        assert config.thinking_level == "medium", (
            f"None duration should default to 'medium', got {config.thinking_level}"
        )

    def test_high_res_video_promotes_to_high(self):
        """High-res video promotes any lower level to 'high'."""
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=30,  # Would be "low" by duration
            is_video=True,
            high_res=True,
        )
        assert config.thinking_level == "high", (
            f"High-res video should promote to 'high', got {config.thinking_level}"
        )

    def test_unsupported_model_returns_none(self):
        """Models without thinking support return None."""
        config = resolve_thinking_config(
            model_name="gemini-2.0-flash",
            duration_s=300,
            is_video=False,
            high_res=False,
        )
        assert config is None, f"Unsupported model should return None, got {config}"

    def test_legacy_model_maps_to_budget(self):
        """Legacy 3.1/2.5 models map to integer thinking_budget."""
        config = resolve_thinking_config(
            model_name="gemini-3.1-flash-lite-preview",
            duration_s=300,
            is_video=False,
            high_res=False,
        )
        assert hasattr(config, "thinking_budget"), (
            "Legacy model should use thinking_budget"
        )
        assert config.thinking_budget == 2048, (
            f"Medium should map to 2048, got {config.thinking_budget}"
        )

    def test_env_var_override(self, monkeypatch):
        """$AGENT_EAR_THINKING_LEVEL env var overrides duration default."""
        monkeypatch.setenv("AGENT_EAR_THINKING_LEVEL", "high")
        config = resolve_thinking_config(
            model_name="gemini-3.5-flash",
            duration_s=30,  # Would be "low" by duration
            is_video=False,
            high_res=False,
        )
        assert config.thinking_level == "high", (
            f"Env var should override, got {config.thinking_level}"
        )
