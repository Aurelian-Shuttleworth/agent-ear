"""Tests for the full validation flow with mocked Gemini client."""

from prompt_validator import validate_briefing, validate_prompt


class TestValidatePrompt:
    """Tests for end-to-end prompt validation with mocked API."""

    def test_empty_prompt_fails(self, mock_genai_client):
        """Empty prompt returns valid=False without calling API."""
        vr, response = validate_prompt(mock_genai_client, "")
        assert vr.valid is False, "Empty prompt should be invalid"
        assert vr.score == 0, "Empty prompt score should be 0"

    def test_valid_prompt_passes(self, mock_genai_client, mock_response):
        """High-score response → valid=True."""
        mock_genai_client.models.generate_content.return_value = mock_response(
            text='{"score": 4, "valid": true, "feedback": "Good prompt", "improved_prompt": null}'
        )
        vr, _ = validate_prompt(
            mock_genai_client,
            "Extract all action items from the meeting, format as bullet list with owners.",
        )
        assert vr.valid is True, f"Should be valid, got score={vr.score}"
        assert vr.score >= 3, f"Score should be ≥3, got {vr.score}"

    def test_low_score_rejects(self, mock_genai_client, mock_response):
        """Low-score response → valid=False."""
        mock_genai_client.models.generate_content.return_value = mock_response(
            text='{"score": 2, "valid": false, "feedback": "Too vague", "improved_prompt": "Better version"}'
        )
        vr, _ = validate_prompt(mock_genai_client, "process audio")
        assert vr.valid is False, "Low-score prompt should be invalid"
        assert vr.improved_prompt is not None, "Should provide improvement suggestion"

    def test_api_error_fails_open(self, mock_genai_client):
        """API error → valid=True, score=3 (fail-open)."""
        mock_genai_client.models.generate_content.side_effect = Exception("API down")
        vr, _ = validate_prompt(mock_genai_client, "Extract all action items from the meeting.")
        assert vr.valid is True, "Should fail open on API error (proceed with recording)"
        assert vr.score == 3, f"Fail-open score should be 3, got {vr.score}"


class TestValidateBriefing:
    """Tests for end-to-end briefing validation with mocked API."""

    def test_static_warnings_included(self, mock_genai_client, mock_response):
        """Static checks (markdown) produce warnings alongside LLM result."""
        mock_genai_client.models.generate_content.return_value = mock_response(
            text='{"score": 4, "valid": true, "feedback": "Fine", "improved_text": null, "improved_notes": null, "warnings": []}'
        )
        bvr, _ = validate_briefing(
            mock_genai_client,
            "## Header in briefing\nSome text",
            director_notes=None,
        )
        assert len(bvr.warnings) > 0, "Should have static warnings for markdown header"

    def test_api_error_returns_static_only(self, mock_genai_client):
        """On API error, returns only static check results."""
        mock_genai_client.models.generate_content.side_effect = Exception("API down")
        bvr, _ = validate_briefing(
            mock_genai_client,
            "Clean briefing text with no issues",
            director_notes=None,
        )
        # Should not crash — returns static results only
        assert bvr is not None, "Should return result even on API error"
