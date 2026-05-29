"""Tests for briefing.py — file parsing and TTS prompt construction."""

from briefing import build_tts_prompt, parse_briefing_file


class TestParseBriefingFile:
    """Tests for briefing file YAML frontmatter parsing."""

    def test_plain_text_no_frontmatter(self, tmp_path):
        """Plain text without frontmatter returns (text, None)."""
        f = tmp_path / "briefing.md"
        f.write_text("Hello, this is a briefing without any frontmatter.")
        text, notes = parse_briefing_file(str(f))
        assert text == "Hello, this is a briefing without any frontmatter.", (
            f"Text should be the full content, got '{text}'"
        )
        assert notes is None, "Notes should be None for plain text"

    def test_with_yaml_frontmatter(self, tmp_path):
        """YAML frontmatter is parsed into dict, text separated."""
        f = tmp_path / "briefing.md"
        f.write_text("---\nstyle: warm\nvoice: Kore\n---\nBriefing body text here.")
        text, notes = parse_briefing_file(str(f))
        assert text == "Briefing body text here.", (
            f"Text should exclude frontmatter, got '{text}'"
        )
        assert notes is not None, "Notes should not be None"
        assert notes.get("style") == "warm", "Should parse style from notes"

    def test_malformed_yaml_fallback(self, tmp_path):
        """Malformed YAML gracefully falls back to full text."""
        f = tmp_path / "briefing.md"
        f.write_text("---\n{invalid: yaml: [broken\n---\nBody text.")
        text, notes = parse_briefing_file(str(f))
        # Should not crash — either parses or falls back
        assert text is not None, "Should always return text"


class TestBuildTtsPrompt:
    """Tests for TTS prompt construction."""

    def test_default_style(self):
        """Default prompt uses warm and natural style when no notes."""
        prompt = build_tts_prompt("Hello world", director_notes=None)
        assert "warm" in prompt.lower() or "natural" in prompt.lower(), (
            "Default should use warm/natural style"
        )

    def test_custom_style_injected(self):
        """Custom style from director_notes is injected into prompt."""
        prompt = build_tts_prompt(
            "Test text", director_notes={"style": "energetic and upbeat"}
        )
        assert "energetic" in prompt.lower(), "Custom style should appear in prompt"

    def test_pace_deliberately_excluded(self):
        """Pace field from notes should NOT appear in prompt text.

        Gemini tends to over-enunciate pace directives, so they're
        intentionally filtered out at the prompt level.
        """
        prompt = build_tts_prompt("Test text", director_notes={"pace": "slow"})
        assert "slow" not in prompt.lower(), "Pace should be excluded from TTS prompt"
