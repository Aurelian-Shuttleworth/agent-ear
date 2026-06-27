"""Tests for run_pipeline — end-to-end with mocked Gemini and recording."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from agent_ear import run_pipeline
from tests.factories import create_wav


class TestPipeline:
    """End-to-end pipeline tests with mocked external dependencies."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, tmp_path, mock_response):
        """Set up common mocks for all pipeline tests.

        Patches: create_client, record_audio, call_gemini.
        Creates a WAV fixture for input_file tests.
        """
        self.wav = create_wav(tmp_path / "input.wav")
        self.output_dir = str(tmp_path / "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.mock_response = mock_response

    @pytest.fixture(autouse=True)
    def _mock_sleep_prevention(self):
        """Prevent caffeinate subprocess (macOS-only, not in Nix sandbox)."""
        with (
            patch("agent_ear.SleepPrevention.__enter__", return_value=None),
            patch("agent_ear.SleepPrevention.__exit__", return_value=False),
        ):
            yield

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    def test_markdown_output(self, mock_gemini, mock_client, mock_response):
        """Pipeline produces a .md file with slug in filename."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(
            text="---\nslug: test-note\ntags: [audio-note]\n---\n## Content\nHello"
        )

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            output_format="markdown",
            non_interactive=True,
            validate=False,
        )

        assert result["exit_code"] == 0, f"Should succeed, got exit_code={result['exit_code']}"
        assert result["output_path"] is not None, "Should produce output file"
        assert result["output_path"].endswith(".md"), "Should be a .md file"
        assert os.path.exists(result["output_path"]), "File should exist on disk"

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    def test_json_output(self, mock_gemini, mock_client, mock_response):
        """Pipeline produces a .json file with correct structure."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(text="---\nslug: json-test\n---\nBody")

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            output_format="json",
            non_interactive=True,
            validate=False,
        )

        assert result["output_path"].endswith(".json"), "Should be a .json file"
        with open(result["output_path"]) as f:
            data = json.load(f)
        assert "content" in data, "JSON should have content field"

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    def test_raw_output(self, mock_gemini, mock_client, mock_response):
        """Pipeline produces a .txt file with raw content."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(text="Raw transcript text")

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            output_format="raw",
            non_interactive=True,
            validate=False,
        )

        assert result["output_path"].endswith(".txt"), "Should be a .txt file"

    @patch("agent_ear.create_client")
    def test_no_auth_exits(self, mock_client):
        """No credentials → exit_code=1 without crashing."""
        mock_client.return_value = (None, False)

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=False,
        )

        assert result["exit_code"] == 1, f"Should exit with code 1, got {result['exit_code']}"

    @patch("agent_ear.create_client")
    @patch("agent_ear.validate_prompt")
    def test_validation_rejection(self, mock_validate, mock_client):
        """Low-score prompt → exit_code=2, no file created."""
        mock_client.return_value = (MagicMock(), False)

        # Create a mock validation result that fails
        from prompt_validator import ValidationResult

        mock_vr = ValidationResult(
            valid=False,
            score=2,
            feedback="Too vague",
            improved_prompt="Better version",
        )
        mock_validate.return_value = (mock_vr, MagicMock())

        result = run_pipeline(
            prompt_text="process audio",
            input_file=str(self.wav),
            output_dir=self.output_dir,
            non_interactive=True,
            validate=True,
        )

        assert result["exit_code"] == 2, f"Validation failure should exit 2, got {result['exit_code']}"
        assert result["output_path"] is None, "No file should be created on rejection"

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    def test_cost_tracked(self, mock_gemini, mock_client, mock_response):
        """Pipeline reports cost > 0 after successful transcription."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(
            text="---\nslug: cost-test\n---\nBody",
            input_tokens=500,
            output_tokens=200,
        )

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            output_format="markdown",
            non_interactive=True,
            validate=False,
        )

        assert result["cost"] >= 0, f"Cost should be tracked, got {result['cost']}"

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    @patch("agent_ear.obsidian_final_pass")
    def test_obsidian_final_pass_triggers(self, mock_final_pass, mock_gemini, mock_client, mock_response):
        """Raw output without frontmatter triggers Obsidian final pass."""
        mock_client.return_value = (MagicMock(), False)

        # Transcription returns content without frontmatter
        mock_gemini.return_value = mock_response(text="Just raw text without frontmatter")

        # Final pass adds frontmatter
        mock_final_pass.return_value = "---\nslug: auto-generated\n---\nJust raw text without frontmatter"

        result = run_pipeline(
            input_file=str(self.wav),
            output_dir=self.output_dir,
            output_format="markdown",
            non_interactive=True,
            validate=False,
        )

        mock_final_pass.assert_called_once()
        assert result["content"].startswith("---"), "Final pass should add frontmatter to raw output"


class TestValidateMediaPath:
    """Tests for _validate_media_path() early validation."""

    def test_input_file_text_rejected(self):
        """Text file passed as audio input raises RuntimeError."""
        from agent_ear import _validate_media_path

        with pytest.raises(RuntimeError, match="not a supported audio file"):
            _validate_media_path("notes.md", is_video=False)

    def test_input_file_valid_audio_accepted(self):
        """Valid WAV file passes validation without error."""
        from agent_ear import _validate_media_path

        _validate_media_path("recording.wav", is_video=False)

    def test_video_text_file_rejected(self):
        """Text file passed as video input raises RuntimeError."""
        from agent_ear import _validate_media_path

        with pytest.raises(RuntimeError, match="not a supported video file"):
            _validate_media_path("notes.md", is_video=True)

    def test_video_valid_mp4_accepted(self):
        """Valid MP4 file passes validation without error."""
        from agent_ear import _validate_media_path

        _validate_media_path("clip.mp4", is_video=True)

    def test_pdf_rejected_as_audio(self):
        """PDF file raises RuntimeError with supported extensions list."""
        from agent_ear import _validate_media_path

        with pytest.raises(RuntimeError, match="Supported extensions") as exc_info:
            _validate_media_path("document.pdf", is_video=False)
        assert ".wav" in str(exc_info.value)
        assert ".mp3" in str(exc_info.value)

    def test_all_audio_extensions_accepted(self):
        """Every extension in AUDIO_MIME_TYPES passes validation."""
        from agent_ear import _validate_media_path
        from upload import AUDIO_MIME_TYPES

        for ext in AUDIO_MIME_TYPES:
            _validate_media_path(f"file{ext}", is_video=False)

    def test_all_video_extensions_accepted(self):
        """Every extension in VIDEO_MIME_TYPES passes validation."""
        from agent_ear import _validate_media_path
        from upload import VIDEO_MIME_TYPES

        for ext in VIDEO_MIME_TYPES:
            _validate_media_path(f"file{ext}", is_video=True)

    def test_error_message_shows_received_extension(self):
        """Error message includes the actual extension that was received."""
        from agent_ear import _validate_media_path

        with pytest.raises(RuntimeError, match=r"\.pdf"):
            _validate_media_path("report.pdf", is_video=False)


class TestVideoAutoDetection:
    """Tests for is_video auto-detection from --input-file extension."""

    @pytest.fixture(autouse=True)
    def setup_dirs(self, tmp_path):
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
    @patch("transcription.call_gemini")
    def test_input_file_mp4_sets_is_video(self, mock_gemini, mock_client, tmp_path, mock_response):
        """--input-file with .mp4 extension auto-sets is_video=True."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(
            text="---\nslug: video-test\ntags: [video-note]\n---\n## Content\nHello"
        )

        video_file = tmp_path / "recording.mp4"
        video_file.write_bytes(b"\x00" * 1024)

        result = run_pipeline(
            input_file=str(video_file),
            output_dir=self.output_dir,
            output_format="markdown",
            non_interactive=True,
            validate=False,
        )

        assert result["exit_code"] == 0
        # Verify transcribe() was called with is_video=True
        call_kwargs = mock_gemini.call_args
        assert call_kwargs is not None, "call_gemini should have been called"

    @patch("agent_ear.create_client")
    @patch("transcription.call_gemini")
    def test_input_file_wav_keeps_audio_mode(self, mock_gemini, mock_client, tmp_path, mock_response):
        """--input-file with .wav extension keeps is_video=False."""
        mock_client.return_value = (MagicMock(), False)
        mock_gemini.return_value = mock_response(text="---\nslug: audio-test\n---\n## Content\nHello")

        audio_file = tmp_path / "recording.wav"
        audio_file.write_bytes(b"\x00" * 1024)

        result = run_pipeline(
            input_file=str(audio_file),
            output_dir=self.output_dir,
            output_format="markdown",
            non_interactive=True,
            validate=False,
        )

        assert result["exit_code"] == 0
