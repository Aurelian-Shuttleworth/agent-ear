"""Tests for agent_ear_cli.py — argument parser validation."""

import pytest

from agent_ear_cli import build_parser


class TestCLIParser:
    """Tests for CLI argument parsing."""

    def test_non_interactive_flag_parsed(self):
        """--non-interactive sets args.non_interactive = True."""
        parser = build_parser()
        args = parser.parse_args(["--non-interactive"])
        assert args.non_interactive is True, "Should parse --non-interactive flag"

    def test_non_interactive_defaults_false(self):
        """Without --non-interactive, the flag defaults to False."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.non_interactive is False, "Should default to False (interactive mode)"

    def test_output_format_choices(self):
        """Invalid format raises SystemExit."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--output-format", "invalid"])

    def test_valid_output_formats(self):
        """All three output formats are accepted."""
        parser = build_parser()
        for fmt in ["markdown", "json", "raw"]:
            args = parser.parse_args(["--output-format", fmt, "--non-interactive"])
            assert args.output_format == fmt, f"Should accept format '{fmt}'"
