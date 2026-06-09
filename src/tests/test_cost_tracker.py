"""Tests for cost_tracker.py — token billing arithmetic."""

from unittest.mock import MagicMock

from cost_tracker import CostTracker


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
