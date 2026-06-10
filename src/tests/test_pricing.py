"""Tests for pricing.py — PriceToken fetch, formatting, and rate resolution."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from cost_tracker import FALLBACK_PRICING
from pricing import (
    INPUT_TOKENS_PER_MINUTE,
    MODEL_MENU,
    OUTPUT_TOKENS_PER_MINUTE,
    _estimate_cost_per_minute,
    fetch_pricing,
    format_model_menu,
    get_rates,
    write_pricing_cache,
)

# --- Fixtures ---


@pytest.fixture()
def sample_api_response():
    """Simulate a PriceToken API response with a subset of models."""
    return {
        "data": [
            {
                "modelId": "gemini-2.5-flash",
                "provider": "google",
                "inputPerMTok": 0.30,
                "outputPerMTok": 2.50,
                "status": "active",
            },
            {
                "modelId": "gemini-2.5-pro",
                "provider": "google",
                "inputPerMTok": 1.25,
                "outputPerMTok": 10.00,
                "status": "active",
            },
        ],
        "meta": {"totalModels": 2},
    }


@pytest.fixture()
def pricing_cache_file(tmp_path):
    """Create a temp pricing cache file."""
    cache = {
        "gemini-3.5-flash": {"input": 1.50, "output": 9.00, "cache": 0.15},
        "gemini-test-model": {"input": 0.50, "output": 3.00, "cache": 0.05},
    }
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(cache))
    return str(path)


# --- fetch_pricing tests ---


class TestFetchPricing:
    """Tests for the fetch_pricing() function."""

    def test_returns_fallback_on_network_error(self):
        """Network errors should return FALLBACK_PRICING unchanged."""
        import urllib.error

        with patch("pricing.urllib.request.urlopen", side_effect=urllib.error.URLError("network")):
            result = fetch_pricing()
        # Should contain all fallback keys
        for key in FALLBACK_PRICING:
            assert key in result, f"Missing fallback key: {key}"

    def test_returns_fallback_on_timeout(self):
        """Timeout should return FALLBACK_PRICING unchanged."""
        with patch("pricing.urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = fetch_pricing()
        assert "gemini-3.5-flash" in result

    def test_returns_fallback_on_json_error(self):
        """Malformed JSON should return FALLBACK_PRICING unchanged."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"not json"
        with patch("pricing.urllib.request.urlopen", return_value=mock_resp):
            result = fetch_pricing()
        assert "gemini-3.5-flash" in result

    def test_merges_api_data_with_fallback(self, sample_api_response):
        """API data should be merged into the result alongside fallback entries."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(sample_api_response).encode()
        with patch("pricing.urllib.request.urlopen", return_value=mock_resp):
            result = fetch_pricing()

        # API model should have updated rates
        assert result["gemini-2.5-flash"]["input"] == 0.30
        assert result["gemini-2.5-flash"]["output"] == 2.50
        # Fallback-only models should still be present
        assert "gemini-3.5-flash" in result

    def test_api_data_preferred_over_fallback(self, sample_api_response):
        """API input/output rates should override fallback values."""
        # Modify API to return different rates than fallback
        sample_api_response["data"][0]["inputPerMTok"] = 99.99
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(sample_api_response).encode()
        with patch("pricing.urllib.request.urlopen", return_value=mock_resp):
            result = fetch_pricing()
        assert result["gemini-2.5-flash"]["input"] == 99.99

    def test_cache_rates_always_from_fallback(self, sample_api_response):
        """Cache rates must always come from FALLBACK_PRICING, not PriceToken."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(sample_api_response).encode()
        with patch("pricing.urllib.request.urlopen", return_value=mock_resp):
            result = fetch_pricing()

        # gemini-2.5-flash has a fallback cache rate of 0.03
        assert result["gemini-2.5-flash"]["cache"] == FALLBACK_PRICING["gemini-2.5-flash"]["cache"]


# --- format_model_menu tests ---


class TestFormatModelMenu:
    """Tests for the format_model_menu() function."""

    def test_includes_cost_per_minute(self):
        """Menu lines should contain a $/min cost estimate."""
        lines = format_model_menu(FALLBACK_PRICING)
        for line in lines:
            assert "$/min" in line or "$0." in line, f"Missing $/min in: {line}"

    def test_produces_correct_number_of_lines(self):
        """Should produce one line per MODEL_MENU entry."""
        lines = format_model_menu(FALLBACK_PRICING)
        assert len(lines) == len(MODEL_MENU)

    def test_lines_contain_emoji_labels(self):
        """Each line should contain the model emoji and label."""
        lines = format_model_menu(FALLBACK_PRICING)
        for (_, emoji, label, _), line in zip(MODEL_MENU, lines):
            assert emoji in line, f"Missing emoji {emoji} in: {line}"
            assert label in line, f"Missing label {label} in: {line}"

    def test_handles_missing_model_gracefully(self):
        """If a model is missing from pricing, should show 'pricing unavailable'."""
        empty_pricing = {}
        lines = format_model_menu(empty_pricing)
        # All models are in FALLBACK_PRICING so they should still have prices
        # But if we truly remove fallback too...
        with patch("pricing.FALLBACK_PRICING", {}):
            lines = format_model_menu({})
        for line in lines:
            assert "unavailable" in line or "$" in line


# --- get_rates tests ---


class TestGetRates:
    """Tests for the get_rates() function."""

    def test_returns_fallback_for_known_model(self):
        """Known model returns FALLBACK_PRICING rates when no cache."""
        rates = get_rates("gemini-3.5-flash")
        assert rates["input"] == 1.50
        assert rates["output"] == 9.00
        assert rates["cache"] == 0.15

    def test_returns_default_for_unknown_model(self):
        """Unknown model falls back to gemini-3.5-flash rates."""
        rates = get_rates("unknown-model-xyz")
        assert rates["input"] == 1.50  # gemini-3.5-flash default

    def test_reads_from_cache_file(self, pricing_cache_file):
        """Should read rates from cache file when available."""
        rates = get_rates("gemini-test-model", cache_path=pricing_cache_file)
        assert rates["input"] == 0.50
        assert rates["output"] == 3.00

    def test_fallback_when_cache_file_missing(self):
        """Should fall back to FALLBACK_PRICING when cache file doesn't exist."""
        rates = get_rates("gemini-3.5-flash", cache_path="/nonexistent/path.json")
        assert rates["input"] == 1.50

    def test_fallback_when_cache_file_corrupt(self, tmp_path):
        """Should fall back when cache file contains invalid JSON."""
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("not json at all")
        rates = get_rates("gemini-3.5-flash", cache_path=str(corrupt))
        assert rates["input"] == 1.50

    def test_fallback_when_model_not_in_cache(self, pricing_cache_file):
        """Should fall back for models not in the cache file."""
        rates = get_rates("gemini-3.1-pro-preview", cache_path=pricing_cache_file)
        assert rates["input"] == FALLBACK_PRICING["gemini-3.1-pro-preview"]["input"]


# --- write_pricing_cache tests ---


class TestWritePricingCache:
    """Tests for the write_pricing_cache() function."""

    def test_writes_valid_json(self):
        """Cache file should contain valid JSON matching input."""
        pricing = {"test-model": {"input": 1.0, "output": 2.0, "cache": 0.1}}
        path = write_pricing_cache(pricing)
        try:
            with open(path) as f:
                data = json.load(f)
            assert data == pricing
        finally:
            os.unlink(path)

    def test_returns_absolute_path(self):
        """Should return an absolute path."""
        pricing = {"test": {"input": 1.0, "output": 2.0, "cache": 0.1}}
        path = write_pricing_cache(pricing)
        try:
            assert os.path.isabs(path)
        finally:
            os.unlink(path)


# --- _estimate_cost_per_minute tests ---


class TestEstimateCostPerMinute:
    """Tests for the cost estimation heuristic."""

    def test_positive_cost(self):
        """Should return a positive cost for non-zero rates."""
        cost = _estimate_cost_per_minute({"input": 1.50, "output": 9.00, "cache": 0.15})
        assert cost > 0

    def test_known_value(self):
        """Verify calculation for gemini-3.5-flash rates."""
        rates = {"input": 1.50, "output": 9.00, "cache": 0.15}
        expected = (INPUT_TOKENS_PER_MINUTE / 1_000_000) * 1.50 + (
            OUTPUT_TOKENS_PER_MINUTE / 1_000_000
        ) * 9.00
        assert abs(_estimate_cost_per_minute(rates) - expected) < 1e-10

    def test_zero_rates(self):
        """Zero rates should produce zero cost."""
        cost = _estimate_cost_per_minute({"input": 0, "output": 0, "cache": 0})
        assert cost == 0.0
