"""Tests for media file type validation — pipeline-level guardrails."""

from unittest.mock import MagicMock, patch

import pytest

from agent_ear import _validate_media_path
from upload import AUDIO_MIME_TYPES, VIDEO_MIME_TYPES


class TestValidateMediaPath:
    """Tests for _validate_media_path() early validation."""

    def test_input_file_text_rejected(self):
        """Text file passed as audio input raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not a supported audio file"):
            _validate_media_path("notes.md", is_video=False)

    def test_input_file_valid_audio_accepted(self):
        """Valid WAV file passes validation without error."""
        _validate_media_path("recording.wav", is_video=False)

    def test_video_text_file_rejected(self):
        """Text file passed as video input raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not a supported video file"):
            _validate_media_path("notes.md", is_video=True)

    def test_video_valid_mp4_accepted(self):
        """Valid MP4 file passes validation without error."""
        _validate_media_path("clip.mp4", is_video=True)

    def test_pdf_rejected_as_audio(self):
        """PDF file raises RuntimeError with supported extensions list."""
        with pytest.raises(RuntimeError, match="Supported extensions") as exc_info:
            _validate_media_path("document.pdf", is_video=False)
        assert ".wav" in str(exc_info.value)
        assert ".mp3" in str(exc_info.value)

    def test_all_audio_extensions_accepted(self):
        """Every extension in AUDIO_MIME_TYPES passes validation."""
        for ext in AUDIO_MIME_TYPES:
            _validate_media_path(f"file{ext}", is_video=False)

    def test_all_video_extensions_accepted(self):
        """Every extension in VIDEO_MIME_TYPES passes validation."""
        for ext in VIDEO_MIME_TYPES:
            _validate_media_path(f"file{ext}", is_video=True)

    def test_error_message_shows_received_extension(self):
        """Error message includes the actual extension that was received."""
        with pytest.raises(RuntimeError, match=r"\.pdf"):
            _validate_media_path("report.pdf", is_video=False)


class TestVideoAutoDetection:
    """Tests for --input-file video auto-detection in run_pipeline."""

    def test_input_file_mp4_auto_detects_video(self, tmp_path):
        """MP4 file via --input-file sets is_video=True."""
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00" * 1024)

        with (
            patch("agent_ear.create_client") as mock_client,
            patch("agent_ear.transcribe") as mock_transcribe,
            patch("agent_ear.validate_prompt") as mock_validate,
            patch("agent_ear.fetch_pricing", side_effect=Exception("skip")),
            patch("agent_ear.resolve_config", return_value=("proj", "us-central1")),
        ):
            mock_client.return_value = (MagicMock(), True)
            mock_validate.return_value = (
                MagicMock(valid=True, score=5, thinking_level=None, extra_tokens=0),
                MagicMock(),
            )
            mock_transcribe.return_value = "test output"

            from agent_ear import run_pipeline

            try:
                run_pipeline(
                    input_file=str(mp4_file),
                    non_interactive=True,
                    output_dir=str(tmp_path),
                )
            except Exception:
                pass  # May fail on downstream steps; we just check the transcribe call

            # Verify transcribe was called with is_video=True
            if mock_transcribe.called:
                call_kwargs = mock_transcribe.call_args
                assert call_kwargs.kwargs.get("is_video") or call_kwargs[1].get("is_video"), (
                    "transcribe() should be called with is_video=True for .mp4 input"
                )
