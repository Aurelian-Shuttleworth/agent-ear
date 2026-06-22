"""Tests for --extra-tokens stacking and clamping logic in run_pipeline."""

import os
from unittest.mock import MagicMock, patch

import pytest

from agent_ear import run_pipeline
from tests.factories import create_wav


class TestExtraTokens:
    """Verify the extra_tokens resolution chain: CLI → env → 0, stacking with
    validator hint, and clamping to 0–16384."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, tmp_path):
        """Common setup: WAV fixture and output directory."""
        self.wav = create_wav(tmp_path / "input.wav")
        self.output_dir = str(tmp_path / "output")
        os.makedirs(self.output_dir, exist_ok=True)

    @pytest.fixture(autouse=True)
    def _mock_sleep_prevention(self):
        """Prevent caffeinate subprocess (macOS-only, not in Nix sandbox)."""
        with (
            patch("agent_ear.SleepPrevention.__enter__", return_value=None),
            patch("agent_ear.SleepPrevention.__exit__", return_value=False),
        ):
            yield

    @patch("agent_ear.create_client")
    @patch("agent_ear.transcribe")
    def test_cli_extra_tokens_passed_to_transcribe(self, mock_transcribe, mock_client):
        """CLI --extra-tokens value reaches transcribe's extra_tokens kwarg."""
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: token-test\n---\nBody"

        run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=False,
            cli_extra_tokens=4096,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 4096, "CLI extra_tokens should be passed through to transcribe"

    @patch("agent_ear.create_client")
    @patch("agent_ear.transcribe")
    def test_env_extra_tokens_fallback(self, mock_transcribe, mock_client, monkeypatch):
        """AGENT_EAR_EXTRA_TOKENS env var used when CLI flag is 0."""
        monkeypatch.setenv("AGENT_EAR_EXTRA_TOKENS", "2048")
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: env-test\n---\nBody"

        run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=False,
            cli_extra_tokens=0,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 2048, "Env var should be used when CLI flag is 0"

    @patch("agent_ear.create_client")
    @patch("agent_ear.transcribe")
    def test_cli_takes_precedence_over_env(self, mock_transcribe, mock_client, monkeypatch):
        """CLI --extra-tokens takes precedence over AGENT_EAR_EXTRA_TOKENS."""
        monkeypatch.setenv("AGENT_EAR_EXTRA_TOKENS", "2048")
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: precedence-test\n---\nBody"

        run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=False,
            cli_extra_tokens=4096,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 4096, "CLI flag should override env var"

    @patch("agent_ear.create_client")
    @patch("agent_ear.validate_prompt")
    @patch("agent_ear.transcribe")
    @patch("agent_ear.CostTracker")
    def test_validator_and_cli_stack(self, mock_tracker_cls, mock_transcribe, mock_validate, mock_client):
        """Validator extra_tokens + CLI extra_tokens stack additively."""
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: stack-test\n---\nBody"

        from prompt_validator import ValidationResult

        mock_vr = ValidationResult(
            valid=True,
            score=5,
            feedback="Great prompt",
            improved_prompt=None,
            thinking_level="low",
            extra_tokens=4096,
        )
        mock_validate.return_value = (mock_vr, MagicMock())

        run_pipeline(
            prompt_text="Extract action items from the meeting.",
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=True,
            cli_extra_tokens=4096,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 8192, (
            f"Validator (4096) + CLI (4096) should stack to 8192, got {kwargs['extra_tokens']}"
        )

    @patch("agent_ear.create_client")
    @patch("agent_ear.validate_prompt")
    @patch("agent_ear.transcribe")
    @patch("agent_ear.CostTracker")
    def test_stacked_tokens_clamped_to_16384(
        self, mock_tracker_cls, mock_transcribe, mock_validate, mock_client
    ):
        """Total extra tokens clamped to 16384 even if sum exceeds it."""
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: clamp-test\n---\nBody"

        from prompt_validator import ValidationResult

        mock_vr = ValidationResult(
            valid=True,
            score=5,
            feedback="Complex prompt",
            improved_prompt=None,
            thinking_level="medium",
            extra_tokens=12000,
        )
        mock_validate.return_value = (mock_vr, MagicMock())

        run_pipeline(
            prompt_text="Detailed multi-speaker meeting analysis.",
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=True,
            cli_extra_tokens=8192,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 16384, f"Should clamp to 16384, got {kwargs['extra_tokens']}"

    @patch("agent_ear.create_client")
    @patch("agent_ear.transcribe")
    def test_zero_extra_tokens_default(self, mock_transcribe, mock_client):
        """No CLI flag and no env var → extra_tokens=0."""
        mock_client.return_value = (MagicMock(), False)
        mock_transcribe.return_value = "---\nslug: zero-test\n---\nBody"

        run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=False,
        )

        _, kwargs = mock_transcribe.call_args
        assert kwargs["extra_tokens"] == 0, "Default should be 0 extra tokens"
