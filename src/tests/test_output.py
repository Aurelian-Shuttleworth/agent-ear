"""Tests for output.py — slug extraction, file saving, and naming."""

import json
import os

from output import extract_slug, sanitize_slug, save_json, save_markdown, save_raw


class TestExtractSlug:
    """Tests for YAML frontmatter slug extraction."""

    def test_from_frontmatter(self):
        """Parses slug from standard YAML frontmatter."""
        content = "---\nslug: my-topic\ntags: [test]\n---\nBody text"
        assert extract_slug(content) == "my-topic", "Should extract slug from frontmatter"

    def test_missing_returns_default(self):
        """Returns 'untitled' when no slug is present."""
        content = "Just some plain text without frontmatter"
        assert extract_slug(content) == "untitled", "Should return default when no slug found"

    def test_custom_default(self):
        """Respects custom default parameter."""
        content = "No slug here"
        assert extract_slug(content, "fallback") == "fallback", "Should return custom default"

    def test_multiline_content(self):
        """Handles slug buried in long multiline content."""
        content = "---\ntags: [a, b]\nslug: deep-nested-slug\nstatus: inbox\n---\n\n## Content\nLots of text"
        assert extract_slug(content) == "deep-nested-slug", "Should find slug in multiline frontmatter"

    def test_slug_with_whitespace(self):
        """Strips leading/trailing whitespace from slug."""
        content = "---\nslug:   spaced-slug  \n---"
        assert extract_slug(content) == "spaced-slug", "Should strip whitespace from slug"


class TestSanitizeSlug:
    """Tests for slug sanitization (ADR 001 — single choke point)."""

    def test_clean_slug_unchanged(self):
        """Already-clean kebab-case slug passes through."""
        assert sanitize_slug("my-clean-slug") == "my-clean-slug", "Clean slug should be unchanged"

    def test_path_separators_stripped(self):
        """Slashes cannot escape the output directory."""
        assert sanitize_slug("notes/2026/evil") == "notes-2026-evil", "Slashes should become hyphens"
        assert sanitize_slug("../../etc/passwd") == "etc-passwd", "Path traversal should be neutralized"

    def test_spaces_and_case_normalized(self):
        """Spaces collapse to hyphens, uppercase is lowered."""
        assert sanitize_slug("My Great Topic") == "my-great-topic", "Should normalize spaces and case"

    def test_unicode_and_symbols_stripped(self):
        """Non-alphanumeric characters collapse to single hyphens."""
        assert sanitize_slug("café & croissants!") == "caf-croissants", "Should strip unicode and symbols"

    def test_empty_falls_back_to_default(self):
        """Nothing left after sanitization → default."""
        assert sanitize_slug("???") == "untitled", "All-symbol slug should fall back to default"
        assert sanitize_slug("", default="fallback") == "fallback", "Empty slug should use custom default"


class TestSaveMarkdown:
    """Tests for markdown file saving."""

    def test_creates_file(self, tmp_output_dir):
        """Creates a .md file in the output directory."""
        content = "---\nslug: test-note\n---\nBody"
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert os.path.exists(path), f"File should exist at {path}"
        assert path.endswith(".md"), "Should have .md extension"

    def test_filename_contains_slug(self, tmp_output_dir):
        """Filename includes the extracted slug."""
        content = "---\nslug: my-topic\n---\nBody"
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert "my-topic" in os.path.basename(path), (
            f"Filename should contain slug, got '{os.path.basename(path)}'"
        )

    def test_llm_slug_with_path_separator_sanitized(self, tmp_output_dir):
        """LLM-generated slug containing a slash cannot break the filename."""
        content = "---\nslug: meeting/notes from today\n---\nBody"
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert os.path.dirname(path) == str(tmp_output_dir), "File must stay in the output directory"
        assert "meeting-notes-from-today" in os.path.basename(path), (
            f"Slug should be sanitized, got '{os.path.basename(path)}'"
        )

    def test_sequential_numbering(self, tmp_output_dir):
        """Second file gets sequence number 002."""
        content = "---\nslug: test\n---\nBody"
        save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        path2 = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert "_002_" in os.path.basename(path2), (
            f"Second file should have seq 002, got '{os.path.basename(path2)}'"
        )

    def test_interactive_custom_topic(self, tmp_output_dir, monkeypatch):
        """Interactive mode: user-provided topic overrides frontmatter slug."""
        content = "---\nslug: original-slug\n---\nBody"
        monkeypatch.setattr("builtins.input", lambda _: "My Custom Topic")
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=False)
        assert "my-custom-topic" in os.path.basename(path), (
            f"Filename should use custom topic slug, got '{os.path.basename(path)}'"
        )

    def test_interactive_empty_input_uses_frontmatter(self, tmp_output_dir, monkeypatch):
        """Interactive mode: pressing Enter (empty input) falls back to frontmatter slug."""
        content = "---\nslug: frontmatter-slug\n---\nBody"
        monkeypatch.setattr("builtins.input", lambda _: "")
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=False)
        assert "frontmatter-slug" in os.path.basename(path), (
            f"Should fall back to frontmatter slug, got '{os.path.basename(path)}'"
        )

    def test_interactive_eoferror_fallback(self, tmp_output_dir, monkeypatch):
        """Interactive mode: EOFError (piped stdin exhausted) falls back gracefully."""
        content = "---\nslug: safe-slug\n---\nBody"

        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=False)
        assert "safe-slug" in os.path.basename(path), (
            f"Should fall back to frontmatter slug on EOFError, got '{os.path.basename(path)}'"
        )

    def test_interactive_keyboard_interrupt_fallback(self, tmp_output_dir, monkeypatch):
        """Interactive mode: Ctrl+C falls back gracefully without crashing."""
        content = "---\nslug: safe-slug\n---\nBody"

        def raise_interrupt(_):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_interrupt)
        path = save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=False)
        assert "safe-slug" in os.path.basename(path), (
            f"Should fall back to frontmatter slug on KeyboardInterrupt, got '{os.path.basename(path)}'"
        )


class TestSaveJson:
    """Tests for JSON file saving."""

    def test_creates_valid_json(self, tmp_output_dir):
        """Creates a valid JSON file with expected structure."""
        content = "---\nslug: json-test\n---\nBody"
        path = save_json(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert os.path.exists(path), f"File should exist at {path}"

        with open(path) as f:
            data = json.load(f)
        assert data["slug"] == "json-test", "JSON should contain slug"
        assert data["format"] == "json", "JSON should contain format"
        assert data["content"] == content, "JSON should contain full content"


class TestSaveRaw:
    """Tests for raw text file saving."""

    def test_creates_txt_file(self, tmp_output_dir):
        """Creates a .txt file with raw content."""
        content = "Just raw text"
        path = save_raw(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        assert path.endswith(".txt"), "Should have .txt extension"
        with open(path) as f:
            assert f.read() == content, "Content should be preserved exactly"
