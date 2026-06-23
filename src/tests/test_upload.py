"""Tests for upload.py — MIME detection, upload routing, and Files API."""

from unittest.mock import MagicMock, patch

import pytest

from config import FILES_API_THRESHOLD, INLINE_THRESHOLD
from upload import detect_mime_type, upload_media


class TestDetectMimeType:
    """Tests for MIME type detection from file extension."""

    def test_audio_wav(self):
        """WAV extension returns audio/wav."""
        assert detect_mime_type("recording.wav", is_video=False) == "audio/wav"

    def test_audio_mp3(self):
        """MP3 extension returns audio/mp3."""
        assert detect_mime_type("interview.mp3", is_video=False) == "audio/mp3"

    def test_audio_m4a(self):
        """M4A extension returns audio/m4a."""
        assert detect_mime_type("voice.m4a", is_video=False) == "audio/m4a"

    def test_audio_flac(self):
        """FLAC extension returns audio/flac."""
        assert detect_mime_type("music.flac", is_video=False) == "audio/flac"

    def test_audio_unknown_extension_raises(self):
        """Unknown audio extension raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported audio file extension"):
            detect_mime_type("data.xyz", is_video=False)

    def test_video_mp4(self):
        """MP4 extension returns video/mp4."""
        assert detect_mime_type("video.mp4", is_video=True) == "video/mp4"

    def test_video_mkv(self):
        """MKV extension returns video/x-matroska."""
        assert detect_mime_type("video.mkv", is_video=True) == "video/x-matroska"

    def test_video_unknown_extension_raises(self):
        """Unknown video extension raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported video file extension"):
            detect_mime_type("video.xyz", is_video=True)

    # --- Additional supported audio formats ---

    def test_audio_aac(self):
        """AAC extension returns audio/aac."""
        assert detect_mime_type("voice.aac", is_video=False) == "audio/aac"

    def test_audio_ogg(self):
        """OGG extension returns audio/ogg."""
        assert detect_mime_type("voice.ogg", is_video=False) == "audio/ogg"

    def test_audio_opus(self):
        """Opus extension returns audio/opus."""
        assert detect_mime_type("voice.opus", is_video=False) == "audio/opus"

    def test_audio_webm(self):
        """WebM audio extension returns audio/webm."""
        assert detect_mime_type("voice.webm", is_video=False) == "audio/webm"

    # --- Additional supported video formats ---

    def test_video_mov(self):
        """MOV extension returns video/quicktime."""
        assert detect_mime_type("clip.mov", is_video=True) == "video/quicktime"

    def test_video_avi(self):
        """AVI extension returns video/x-msvideo."""
        assert detect_mime_type("clip.avi", is_video=True) == "video/x-msvideo"

    def test_video_webm(self):
        """WebM video extension returns video/webm."""
        assert detect_mime_type("clip.webm", is_video=True) == "video/webm"

    # --- Invalid input rejection ---

    def test_audio_text_file_raises(self):
        """Markdown file raises ValueError when treated as audio."""
        with pytest.raises(ValueError, match="Unsupported audio file extension"):
            detect_mime_type("notes.md", is_video=False)

    def test_audio_python_file_raises(self):
        """Python file raises ValueError when treated as audio."""
        with pytest.raises(ValueError, match="Unsupported audio file extension"):
            detect_mime_type("script.py", is_video=False)

    def test_audio_no_extension_raises(self):
        """File without extension raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported audio file extension"):
            detect_mime_type("recording", is_video=False)

    def test_video_audio_extension_raises(self):
        """Audio extension raises ValueError when treated as video."""
        with pytest.raises(ValueError, match="Unsupported video file extension"):
            detect_mime_type("audio.wav", is_video=True)

    def test_video_text_file_raises(self):
        """Text file raises ValueError when treated as video."""
        with pytest.raises(ValueError, match="Unsupported video file extension"):
            detect_mime_type("notes.txt", is_video=True)

    def test_error_message_lists_supported_extensions(self):
        """Error message includes the list of supported extensions."""
        with pytest.raises(ValueError, match=r"\.wav") as exc_info:
            detect_mime_type("bad.xyz", is_video=False)
        # Should list all supported audio extensions
        assert ".mp3" in str(exc_info.value)
        assert ".flac" in str(exc_info.value)


class TestUploadMediaInline:
    """Tests for inline upload path (files ≤ 100 MB)."""

    def test_inline_upload_small_file(self, small_wav):
        """File ≤100MB uses inline Part.from_bytes upload."""
        client = MagicMock()
        with patch("upload.types.Part") as mock_part:
            upload_media(
                client,
                str(small_wav),
                "audio/wav",
                project_id=None,
                is_vertex=False,
                non_interactive=True,
            )
            mock_part.from_bytes.assert_called_once()


class TestUploadMediaFilesAPI:
    """Tests for Gemini Files API upload path (AI Studio, > 100 MB ≤ 2 GB)."""

    def test_files_api_used_for_large_ai_studio_file(self, tmp_path):
        """AI Studio + file > 100 MB → calls client.files.upload."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        # Mock the uploaded file to be immediately ACTIVE
        mock_file = MagicMock()
        mock_file.state.name = "ACTIVE"
        mock_file.name = "files/test-123"
        client.files.upload.return_value = mock_file

        result = upload_media(
            client,
            str(large_file),
            "audio/wav",
            project_id=None,
            is_vertex=False,
            non_interactive=True,
        )

        client.files.upload.assert_called_once_with(file=str(large_file))
        assert result is mock_file

    def test_files_api_polls_until_active(self, tmp_path):
        """Files API polls PROCESSING → ACTIVE transition."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()

        # First upload returns PROCESSING, then get returns ACTIVE
        processing_file = MagicMock()
        processing_file.state.name = "PROCESSING"
        processing_file.name = "files/test-123"

        active_file = MagicMock()
        active_file.state.name = "ACTIVE"
        active_file.name = "files/test-123"

        client.files.upload.return_value = processing_file
        client.files.get.return_value = active_file

        with patch("upload.time.sleep"):
            result = upload_media(
                client,
                str(large_file),
                "audio/wav",
                project_id=None,
                is_vertex=False,
                non_interactive=True,
            )

        assert result is active_file
        client.files.get.assert_called_with(name="files/test-123")

    def test_files_api_timeout_raises(self, tmp_path):
        """Files API raises RuntimeError after poll timeout."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        stuck_file = MagicMock()
        stuck_file.state.name = "PROCESSING"
        stuck_file.name = "files/stuck-file"
        client.files.upload.return_value = stuck_file
        client.files.get.return_value = stuck_file  # Never becomes ACTIVE

        with (
            patch("upload.time.sleep"),
            patch("upload.FILES_API_POLL_TIMEOUT", 10),
            patch("upload.FILES_API_POLL_INTERVAL", 5),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                upload_media(
                    client,
                    str(large_file),
                    "audio/wav",
                    project_id=None,
                    is_vertex=False,
                    non_interactive=True,
                )

    def test_files_api_failed_state_raises(self, tmp_path):
        """Files API raises RuntimeError when processing fails."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        failed_file = MagicMock()
        failed_file.state.name = "FAILED"
        failed_file.name = "files/failed-file"
        client.files.upload.return_value = failed_file

        with pytest.raises(RuntimeError, match="processing failed"):
            upload_media(
                client,
                str(large_file),
                "audio/wav",
                project_id=None,
                is_vertex=False,
                non_interactive=True,
            )

    def test_files_api_over_2gb_raises(self, tmp_path, monkeypatch):
        """AI Studio + file > 2 GB → RuntimeError with --gcs-bucket suggestion."""
        large_file = tmp_path / "huge.wav"
        large_file.write_bytes(b"\x00" * 1024)  # Small physical file

        client = MagicMock()
        # Mock os.path.getsize to return > 2 GB without creating a huge file
        with patch("upload.os.path.getsize", return_value=FILES_API_THRESHOLD + 1):
            with pytest.raises(RuntimeError, match="too large"):
                upload_media(
                    client,
                    str(large_file),
                    "audio/wav",
                    project_id=None,
                    is_vertex=False,
                    non_interactive=True,
                )


class TestUploadMediaGCS:
    """Tests for GCS upload path."""

    def test_explicit_gcs_bucket_overrides_files_api(self, tmp_path):
        """--gcs-bucket set + AI Studio → GCS used (not Files API)."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        with (
            patch("upload._upload_to_gcs", return_value="gs://my-bucket/staging/test") as mock_gcs,
            patch("upload.types.Part") as mock_part,
        ):
            upload_media(
                client,
                str(large_file),
                "audio/wav",
                project_id=None,
                bucket_name="my-bucket",
                is_vertex=False,
                non_interactive=True,
            )
            mock_gcs.assert_called_once()
            mock_part.from_uri.assert_called_once()
            # Files API should NOT be called
            client.files.upload.assert_not_called()

    def test_explicit_gcs_env_var_overrides(self, tmp_path, monkeypatch):
        """$AGENT_EAR_GCS_BUCKET env var triggers GCS path."""
        monkeypatch.setenv("AGENT_EAR_GCS_BUCKET", "env-bucket")
        small_file = tmp_path / "small.wav"
        small_file.write_bytes(b"\x00" * 1024)  # Even small files go GCS

        client = MagicMock()
        with (
            patch("upload._upload_to_gcs", return_value="gs://env-bucket/staging/test") as mock_gcs,
            patch("upload.types.Part"),
        ):
            upload_media(
                client,
                str(small_file),
                "audio/wav",
                project_id=None,
                is_vertex=False,
                non_interactive=True,
            )
            mock_gcs.assert_called_once()

    def test_vertex_large_file_uses_gcs(self, tmp_path):
        """Vertex AI + file > 100 MB → GCS (not Files API)."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        with (
            patch("upload._upload_to_gcs", return_value="gs://proj-bucket/staging/test") as mock_gcs,
            patch("upload.types.Part"),
            patch("upload.resolve_gcs_bucket", return_value="proj-bucket"),
        ):
            upload_media(
                client,
                str(large_file),
                "audio/wav",
                project_id="my-project",
                is_vertex=True,
                non_interactive=True,
            )
            mock_gcs.assert_called_once()
            client.files.upload.assert_not_called()

    def test_gcs_no_bucket_configured_raises(self, tmp_path):
        """GCS path with no resolvable bucket raises RuntimeError."""
        large_file = tmp_path / "large.wav"
        large_file.write_bytes(b"\x00" * (INLINE_THRESHOLD + 1))

        client = MagicMock()
        with patch("upload.resolve_gcs_bucket", return_value=None):
            with pytest.raises(RuntimeError, match="No GCS bucket configured"):
                upload_media(
                    client,
                    str(large_file),
                    "audio/wav",
                    project_id=None,
                    bucket_name="my-bucket",
                    is_vertex=True,
                    non_interactive=True,
                )
