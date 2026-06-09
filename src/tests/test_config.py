"""Tests for config.py — 4-tier resolution chain and client creation."""

import os
from unittest.mock import MagicMock, patch

from config import create_client, resolve_config, resolve_gcs_bucket, resolve_output_dir


class TestResolveOutputDir:
    """Tests for output directory resolution: CLI → env → cwd."""

    def test_cli_takes_priority(self, env_clean, monkeypatch, tmp_path):
        """CLI argument overrides env var and cwd default."""
        monkeypatch.setenv("AGENT_EAR_OUTPUT_DIR", "/from/env")
        result = resolve_output_dir(str(tmp_path))
        assert result == str(tmp_path), f"CLI arg should take priority, got '{result}'"

    def test_env_fallback(self, env_clean, monkeypatch, tmp_path):
        """AGENT_EAR_OUTPUT_DIR env var used when no CLI arg."""
        monkeypatch.setenv("AGENT_EAR_OUTPUT_DIR", str(tmp_path))
        result = resolve_output_dir(None)
        assert result == str(tmp_path), f"Should fall back to env var, got '{result}'"

    def test_cwd_default(self, env_clean):
        """Falls back to os.getcwd() when nothing else is set."""
        result = resolve_output_dir(None)
        assert result == os.getcwd(), f"Should fall back to cwd, got '{result}'"


class TestResolveConfig:
    """Tests for project/location resolution: CLI → env → gcloud."""

    def test_cli_project(self, env_clean, monkeypatch):
        """CLI project_id is used over env/gcloud."""
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        project, location = resolve_config("cli-project", "us-central1")
        assert project == "cli-project", f"CLI project should take priority, got '{project}'"

    def test_env_fallback(self, env_clean, monkeypatch):
        """GOOGLE_CLOUD_PROJECT env var used when no CLI arg."""
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        project, _ = resolve_config(None, "us-central1")
        assert project == "env-project", f"Should fall back to env var, got '{project}'"

    @patch("config.subprocess.run")
    def test_gcloud_fallback(self, mock_run, env_clean):
        """Falls back to gcloud config when no CLI/env."""
        mock_run.return_value = MagicMock(returncode=0, stdout="gcloud-project\n")
        project, _ = resolve_config(None, "us-central1")
        assert project == "gcloud-project", f"Should fall back to gcloud config, got '{project}'"

    @patch("config.subprocess.run")
    def test_no_project(self, mock_run, env_clean):
        """Returns None when nothing is configured."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        project, _ = resolve_config(None, "us-central1")
        assert project is None, f"Should return None when nothing configured, got '{project}'"

    def test_location_passthrough(self, env_clean):
        """Location is passed through unchanged."""
        _, location = resolve_config(None, "europe-west4")
        assert location == "europe-west4", f"Location should pass through, got '{location}'"


class TestResolveGcsBucket:
    """Tests for GCS bucket name resolution."""

    def test_explicit_bucket(self):
        """Explicit bucket name used directly."""
        result = resolve_gcs_bucket("my-bucket", "my-project")
        assert result == "my-bucket", f"Explicit bucket should be used, got '{result}'"

    def test_derived_from_project(self):
        """Derives bucket name from project ID."""
        result = resolve_gcs_bucket(None, "my-project")
        assert result == "my-project-transcribe-staging", f"Should derive from project, got '{result}'"


class TestCreateClient:
    """Tests for client creation: Vertex AI → API key → None."""

    @patch("config.genai.Client")
    def test_vertex_with_project(self, mock_client_cls, env_clean):
        """Returns (client, True) when project is available."""
        client, is_vertex = create_client("my-project", "us-central1")
        assert is_vertex is True, "Should be Vertex AI mode with project"
        assert client is not None, "Client should not be None"

    @patch("config.genai.Client")
    def test_api_key_fallback(self, mock_client_cls, env_clean, monkeypatch):
        """Returns (client, False) when only API key is set."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
        client, is_vertex = create_client(None, "us-central1")
        assert is_vertex is False, "Should be AI Studio mode with API key"
        assert client is not None, "Client should not be None"

    def test_no_auth_returns_none(self, env_clean):
        """Returns (None, False) when nothing is configured."""
        client, is_vertex = create_client(None, "us-central1")
        assert client is None, "Client should be None with no auth"
        assert is_vertex is False, "Should not be Vertex mode"
