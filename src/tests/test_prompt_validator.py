"""Tests for prompt_validator.py — static checks and JSON response parsing."""

from prompt_validator import (
    _parse_briefing_validation_response,
    _parse_validation_response,
    _static_briefing_checks,
)


class TestStaticBriefingChecks:
    """Tests for static (no-LLM) briefing text checks."""

    def test_detects_markdown_headers(self):
        """Markdown headers (##) trigger a warning."""
        warnings, _ = _static_briefing_checks("## This is a header\nSome text", None)
        assert any(
            "markdown" in w.lower() or "header" in w.lower() or "non-speakable" in w.lower() for w in warnings
        ), f"Should detect markdown headers, got warnings: {warnings}"

    def test_detects_urls(self):
        """URLs trigger a warning (not speakable in TTS)."""
        warnings, _ = _static_briefing_checks("Visit https://example.com for details", None)
        assert any("url" in w.lower() or "link" in w.lower() for w in warnings), (
            f"Should detect URLs, got warnings: {warnings}"
        )

    def test_long_text_warning(self):
        """Very long text (>500 words) triggers length warning."""
        long_text = " ".join(["word"] * 600)
        warnings, _ = _static_briefing_checks(long_text, None)
        assert any("long" in w.lower() or "length" in w.lower() or "word" in w.lower() for w in warnings), (
            f"Should warn about length, got warnings: {warnings}"
        )

    def test_clean_text_no_warnings(self):
        """Clean, short spoken text produces no warnings."""
        warnings, _ = _static_briefing_checks(
            "Good morning! Today we'll discuss three important topics.", None
        )
        assert len(warnings) == 0, f"Clean text should produce no warnings, got: {warnings}"


class TestParseValidationResponse:
    """Tests for prompt validation JSON response parsing."""

    def test_valid_json(self):
        """Well-formed JSON is parsed correctly."""
        raw = '{"score": 4, "valid": true, "feedback": "Good prompt", "improved_prompt": null}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.score == 4, f"Score should be 4, got {result.score}"
        assert result.valid is True, "Should be valid"
        assert result.feedback == "Good prompt"

    def test_json_with_fences(self):
        """JSON wrapped in ```json``` fences is stripped and parsed."""
        raw = '```json\n{"score": 3, "valid": true, "feedback": "OK"}\n```'
        result = _parse_validation_response(raw, min_score=3)
        assert result.score == 3, f"Score should be 3, got {result.score}"

    def test_malformed_json_fallback(self):
        """Malformed JSON returns a graceful fallback result."""
        raw = "this is not json at all {broken"
        result = _parse_validation_response(raw, min_score=3)
        # Should not crash — returns a conservative fallback
        assert result is not None, "Should return a result even on bad JSON"
        assert result.valid is False, "Fallback should be invalid (conservative)"

    def test_score_clamped_to_5(self):
        """Score values > 5 are clamped to 5."""
        raw = '{"score": 99, "valid": true, "feedback": "Amazing"}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.score <= 5, f"Score should be clamped to 5, got {result.score}"


class TestParseBriefingValidationResponse:
    """Tests for briefing validation JSON response parsing."""

    def test_with_fixes(self):
        """Parses improved_text and improved_notes correctly."""
        raw = '{"score": 4, "valid": true, "feedback": "Minor fix", "improved_text": "Fixed text", "improved_notes": {"style": "calm"}, "warnings": []}'
        result = _parse_briefing_validation_response(raw, min_score=3)
        assert result.improved_text == "Fixed text", (
            f"Should parse improved_text, got '{result.improved_text}'"
        )
        assert result.improved_notes == {"style": "calm"}, (
            f"Should parse improved_notes, got '{result.improved_notes}'"
        )

    def test_malformed_briefing_fallback(self):
        """Malformed JSON returns graceful fallback."""
        raw = "not json"
        result = _parse_briefing_validation_response(raw, min_score=3)
        assert result is not None, "Should return a result even on bad JSON"


class TestThinkingHintsParsing:
    """Tests for thinking_level and extra_tokens fields in validation response."""

    def test_full_response_with_hints(self):
        """All fields including thinking hints are parsed correctly."""
        raw = '{"score": 4, "valid": true, "feedback": "Good", "improved_prompt": null, "thinking_level": "high", "extra_tokens": 4096}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.thinking_level == "high", f"Expected 'high', got {result.thinking_level}"
        assert result.extra_tokens == 4096, f"Expected 4096, got {result.extra_tokens}"

    def test_backward_compat_missing_hints(self):
        """Absent thinking_level and extra_tokens default to None/0."""
        raw = '{"score": 4, "valid": true, "feedback": "Good"}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.thinking_level is None, (
            f"Missing thinking_level should be None, got {result.thinking_level}"
        )
        assert result.extra_tokens == 0, f"Missing extra_tokens should be 0, got {result.extra_tokens}"

    def test_invalid_thinking_level_ignored(self):
        """Invalid thinking_level values are treated as None."""
        raw = '{"score": 4, "valid": true, "feedback": "Good", "thinking_level": "maximum"}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.thinking_level is None, f"Invalid level should be None, got {result.thinking_level}"

    def test_extra_tokens_clamped_to_max(self):
        """extra_tokens values above 16384 are clamped."""
        raw = '{"score": 4, "valid": true, "feedback": "Good", "extra_tokens": 99999}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.extra_tokens == 16384, f"Should be clamped to 16384, got {result.extra_tokens}"

    def test_extra_tokens_negative_clamped_to_zero(self):
        """Negative extra_tokens values are clamped to 0."""
        raw = '{"score": 4, "valid": true, "feedback": "Good", "extra_tokens": -100}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.extra_tokens == 0, f"Negative should be clamped to 0, got {result.extra_tokens}"

    def test_extra_tokens_non_numeric_defaults_zero(self):
        """Non-numeric extra_tokens values default to 0."""
        raw = '{"score": 4, "valid": true, "feedback": "Good", "extra_tokens": "many"}'
        result = _parse_validation_response(raw, min_score=3)
        assert result.extra_tokens == 0, f"Non-numeric should default to 0, got {result.extra_tokens}"
