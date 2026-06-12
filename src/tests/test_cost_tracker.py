"""Tests for cost_tracker.py — token billing arithmetic."""

import json
from unittest.mock import MagicMock

import pytest

from cost_tracker import FALLBACK_PRICING, CostTracker


def _make_response(input_tokens=100, output_tokens=50, thinking_tokens=0, cached_tokens=0):
    """Helper to create a mock response with usage_metadata."""
    r = MagicMock()
    r.usage_metadata.prompt_token_count = input_tokens
    r.usage_metadata.candidates_token_count = output_tokens
    r.usage_metadata.thoughts_token_count = thinking_tokens
    r.usage_metadata.cached_content_token_count = cached_tokens
    r.usage_metadata.total_token_count = input_tokens + output_tokens + thinking_tokens
    return r


class TestCostTracker:
    """Tests for CostTracker token billing and cost calculation."""

    def test_track_basic_cost(self):
        """Input + output tokens compute to a positive USD cost."""
        tracker = CostTracker()
        tracker.track(
            "gemini-2.0-flash-lite",
            _make_response(input_tokens=1000, output_tokens=500),
        )
        assert tracker.total_cost_usd > 0, f"Cost should be positive, got {tracker.total_cost_usd}"

    def test_track_with_thinking_tokens(self):
        """Thinking tokens billed at output rate increase total cost."""
        tracker_no_think = CostTracker()
        tracker_no_think.track(
            "gemini-2.0-flash-lite",
            _make_response(input_tokens=1000, output_tokens=500),
        )

        tracker_with_think = CostTracker()
        tracker_with_think.track(
            "gemini-2.0-flash-lite",
            _make_response(input_tokens=1000, output_tokens=500, thinking_tokens=200),
        )

        assert tracker_with_think.total_cost_usd > tracker_no_think.total_cost_usd, (
            "Thinking tokens should increase cost"
        )

    def test_track_with_cached_tokens(self):
        """Cached tokens should reduce cost vs uncached."""
        tracker_uncached = CostTracker()
        tracker_uncached.track(
            "gemini-2.0-flash-lite",
            _make_response(input_tokens=1000, output_tokens=500),
        )

        tracker_cached = CostTracker()
        tracker_cached.track(
            "gemini-2.0-flash-lite",
            _make_response(input_tokens=1000, output_tokens=500, cached_tokens=800),
        )

        assert tracker_cached.total_cost_usd < tracker_uncached.total_cost_usd, (
            "Cached tokens should reduce cost"
        )

    def test_total_cost_multiple_calls(self):
        """Total cost sums across multiple tracked calls."""
        tracker = CostTracker()
        tracker.track("gemini-2.0-flash-lite", _make_response(input_tokens=100, output_tokens=50))
        first_cost = tracker.total_cost_usd

        tracker.track("gemini-2.0-flash-lite", _make_response(input_tokens=200, output_tokens=100))
        assert tracker.total_cost_usd > first_cost, "Second call should increase total cost"

    def test_zero_tokens(self):
        """Zero tokens should produce zero cost without error."""
        tracker = CostTracker()
        tracker.track("gemini-2.0-flash-lite", _make_response(input_tokens=0, output_tokens=0))
        assert tracker.total_cost_usd == 0.0, (
            f"Zero tokens should produce zero cost, got {tracker.total_cost_usd}"
        )

    def test_unknown_model_does_not_crash(self):
        """Unknown model name should not raise — uses fallback pricing."""
        tracker = CostTracker()
        # Should not raise
        tracker.track("unknown-model-xyz", _make_response(input_tokens=100, output_tokens=50))
        assert tracker.total_cost_usd >= 0, "Should produce a non-negative cost"

    def test_pricing_cache_parameter(self, tmp_path):
        """CostTracker with pricing_cache should use rates from cache file."""
        cache = {
            "test-model": {"input": 10.0, "output": 50.0, "cache": 1.0},
        }
        cache_path = tmp_path / "pricing.json"
        cache_path.write_text(json.dumps(cache))

        tracker = CostTracker(pricing_cache=str(cache_path))
        tracker.track("test-model", _make_response(input_tokens=1_000_000, output_tokens=500_000))

        # Expected: (1M / 1M) * 10.0 + (500K / 1M) * 50.0 = 10.0 + 25.0 = 35.0
        assert tracker.total_cost_usd == pytest.approx(35.0, rel=0.01)

    def test_pricing_cache_fallback_on_missing_file(self):
        """CostTracker with invalid cache path should fall back to hardcoded rates."""
        tracker = CostTracker(pricing_cache="/nonexistent/pricing.json")
        tracker.track("gemini-3.5-flash", _make_response(input_tokens=1000, output_tokens=500))
        assert tracker.total_cost_usd > 0

    def test_fallback_pricing_dict_has_expected_models(self):
        """FALLBACK_PRICING should contain our primary models."""
        assert "gemini-3.5-flash" in FALLBACK_PRICING
        assert "gemini-3.1-pro-preview" in FALLBACK_PRICING
        assert "gemini-3.1-flash-lite-preview" in FALLBACK_PRICING
