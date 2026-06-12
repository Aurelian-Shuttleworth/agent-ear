"""Shared test fixtures for agent-ear test suite."""

import os
from unittest.mock import MagicMock

import pytest

from tests.factories import create_wav


@pytest.fixture
def mock_genai_client():
    """Mock google-genai Client with configurable generate_content."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_response():
    """Factory for fake Gemini API responses with configurable fields.

    Returns a callable that creates mock responses with proper
    usage_metadata structure for CostTracker compatibility.
    """

    def _make(
        text="test output",
        finish_reason="STOP",
        input_tokens=100,
        output_tokens=50,
        thinking_tokens=0,
        cached_tokens=0,
    ):
        response = MagicMock()
        response.text = text

        candidate = MagicMock()
        candidate.finish_reason = finish_reason
        response.candidates = [candidate]

        # Usage metadata matching Gemini API structure
        response.usage_metadata.prompt_token_count = input_tokens
        response.usage_metadata.candidates_token_count = output_tokens
        response.usage_metadata.thoughts_token_count = thinking_tokens
        response.usage_metadata.cached_content_token_count = cached_tokens
        response.usage_metadata.total_token_count = input_tokens + output_tokens + thinking_tokens
        return response

    return _make


@pytest.fixture
def env_clean(monkeypatch):
    """Unset all GOOGLE_* and AGENT_EAR_* environment variables.

    Ensures tests don't leak auth state from the host environment.
    """
    for key in list(os.environ.keys()):
        if key.startswith(("GOOGLE_", "AGENT_EAR_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Provide a clean temporary directory for output file tests."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def wav_fixture(tmp_path_factory):
    """Session-compatible WAV fixture — 1s silent WAV.

    Uses tmp_path_factory for broader scope compatibility.
    """
    path = tmp_path_factory.mktemp("audio") / "test.wav"
    return create_wav(path, duration_s=1.0)


@pytest.fixture
def small_wav(tmp_path):
    """Function-scoped WAV fixture for tests that modify/delete the file."""
    path = tmp_path / "test.wav"
    return create_wav(path, duration_s=0.5)
