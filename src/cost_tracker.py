"""Cost tracking via CostTracker pattern per gemini-ai/cost-tracking.md.

Tracks all token types: input, output, thinking, and cached.
Thinking tokens are billed at the output rate.
Cached tokens are billed at reduced rate.

Copied from transcribe-tool — separate package to avoid shared library.
"""

from dataclasses import dataclass, field

# Pricing per 1M tokens (USD) — last verified 2026-06-10
PRICING = {
    # Gemini 3.5
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00, "cache": 0.15},
    # Gemini 3.x
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00, "cache": 0.05},
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50, "cache": 0.025},
    "gemini-3.1-flash-lite": {
        "input": 0.25,
        "output": 1.50,
        "cache": 0.025,
    },  # GA (replaces preview Jul 9 2026)
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00, "cache": 0.20},
    # Gemini 2.x (legacy)
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cache": 0.03},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40, "cache": 0.01},
    "gemini-2.5-flash-tts": {"input": 0.30, "output": 2.50, "cache": 0.03},
    "gemini-2.5-flash-preview-tts": {"input": 0.30, "output": 2.50, "cache": 0.03},
}


@dataclass
class UsageReport:
    model: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cached_tokens: int
    total_tokens: int
    cost_usd: float


@dataclass
class CostTracker:
    reports: list[UsageReport] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.reports)

    def track(self, model, response):
        """Track usage from a generate_content response."""
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        thinking_tokens = getattr(usage, "thoughts_token_count", 0) or 0
        cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0

        rates = PRICING.get(model, PRICING["gemini-3.5-flash"])
        billable_input = input_tokens - cached_tokens
        cost = (
            (billable_input / 1_000_000) * rates["input"]
            + ((output_tokens + thinking_tokens) / 1_000_000) * rates["output"]
            + (cached_tokens / 1_000_000) * rates["cache"]
        )
        report = UsageReport(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            cached_tokens=cached_tokens,
            total_tokens=getattr(usage, "total_token_count", 0) or 0,
            cost_usd=round(cost, 6),
        )
        self.reports.append(report)
        return report

    def print_summary(self):
        """Print human-readable cost summary."""
        for r in self.reports:
            print(
                f"💰 {r.model}: ${r.cost_usd:.4f} "
                f"(in: {r.input_tokens:,}, out: {r.output_tokens:,}, "
                f"think: {r.thinking_tokens:,})"
            )
        if len(self.reports) > 1:
            print(f"💰 Total: ${self.total_cost_usd:.4f}")
