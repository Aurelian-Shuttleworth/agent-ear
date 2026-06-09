"""Tests for output.py — slug extraction, file saving, and naming."""

import json
import os


from output import extract_slug, save_json, save_markdown, save_raw


class TestExtractSlug:
    """Tests for YAML frontmatter slug extraction."""

    def test_from_frontmatter(self):
        """Parses slug from standard YAML frontmatter."""
        content = "---\nslug: my-topic\ntags: [test]\n---\nBody text"
        assert extract_slug(content) == "my-topic", (
            "Should extract slug from frontmatter"
        )

    def test_missing_returns_default(self):
        """Returns 'untitled' when no slug is present."""
        content = "Just some plain text without frontmatter"
        assert extract_slug(content) == "untitled", (
            "Should return default when no slug found"
        )

    def test_custom_default(self):
        """Respects custom default parameter."""
        content = "No slug here"
        assert extract_slug(content, "fallback") == "fallback", (
            "Should return custom default"
        )

    def test_multiline_content(self):
        """Handles slug buried in long multiline content."""
        content = "---\ntags: [a, b]\nslug: deep-nested-slug\nstatus: inbox\n---\n\n## Content\nLots of text"
        assert extract_slug(content) == "deep-nested-slug", (
            "Should find slug in multiline frontmatter"
        )

    def test_slug_with_whitespace(self):
        """Strips leading/trailing whitespace from slug."""
        content = "---\nslug:   spaced-slug  \n---"
        assert extract_slug(content) == "spaced-slug", (
            "Should strip whitespace from slug"
        )


class TestSaveMarkdown:
    """Tests for markdown file saving."""

    def test_creates_file(self, tmp_output_dir):
        """Creates a .md file in the output directory."""
        content = "---\nslug: test-note\n---\nBody"
        path = save_markdown(
            content, str(tmp_output_dir), "2026-05-23", non_interactive=True
        )
        assert os.path.exists(path), f"File should exist at {path}"
        assert path.endswith(".md"), "Should have .md extension"

    def test_filename_contains_slug(self, tmp_output_dir):
        """Filename includes the extracted slug."""
        content = "---\nslug: my-topic\n---\nBody"
        path = save_markdown(
            content, str(tmp_output_dir), "2026-05-23", non_interactive=True
        )
        assert "my-topic" in os.path.basename(path), (
            f"Filename should contain slug, got '{os.path.basename(path)}'"
        )

    def test_sequential_numbering(self, tmp_output_dir):
        """Second file gets sequence number 002."""
        content = "---\nslug: test\n---\nBody"
        save_markdown(content, str(tmp_output_dir), "2026-05-23", non_interactive=True)
        path2 = save_markdown(
            content, str(tmp_output_dir), "2026-05-23", non_interactive=True
        )
        assert "_002_" in os.path.basename(path2), (
            f"Second file should have seq 002, got '{os.path.basename(path2)}'"
        )


class TestSaveJson:
    """Tests for JSON file saving."""

    def test_creates_valid_json(self, tmp_output_dir):
        """Creates a valid JSON file with expected structure."""
        content = "---\nslug: json-test\n---\nBody"
        path = save_json(
            content, str(tmp_output_dir), "2026-05-23", non_interactive=True
        )
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
        path = save_raw(
            content, str(tmp_output_dir), "2026-05-23", non_interactive=True
        )
        assert path.endswith(".txt"), "Should have .txt extension"
        with open(path) as f:
            assert f.read() == content, "Content should be preserved exactly"
