"""Tests for agent_ear_cli.py — argument parser validation."""

import pytest

from agent_ear_cli import build_parser


class TestCLIParser:
    """Tests for CLI argument parsing."""

    def test_auto_flag_parsed(self):
        """--auto sets args.auto = True."""
        parser = build_parser()
        args = parser.parse_args(["--auto"])
        assert args.auto is True, "Should parse --auto flag"

    def test_output_format_choices(self):
        """Invalid format raises SystemExit."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--output-format", "invalid"])

    def test_valid_output_formats(self):
        """All three output formats are accepted."""
        parser = build_parser()
        for fmt in ["markdown", "json", "raw"]:
            args = parser.parse_args(["--output-format", fmt, "--auto"])
            assert args.output_format == fmt, f"Should accept format '{fmt}'"
