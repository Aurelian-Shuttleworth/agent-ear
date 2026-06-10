"""Live pricing via PriceToken API with hardcoded fallback.

Fetches model pricing from https://pricetoken.ai/api/v1/text,
merges with FALLBACK_PRICING from cost_tracker.py, and provides:
  - fetch_pricing()      → merged pricing dict
  - format_model_menu()  → gum-formatted menu strings with $/min
  - get_rates()          → rates for a specific model (cache-aware)
"""

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from typing import TypedDict

from cost_tracker import FALLBACK_PRICING

# --- Constants ---

PRICETOKEN_URL = "https://pricetoken.ai/api/v1/text"
PRICETOKEN_TIMEOUT = 2.0  # seconds

# Token-per-minute heuristics for transcription cost estimation.
# Based on observed usage across audio and video transcription runs.
INPUT_TOKENS_PER_MINUTE = 1500  # prompt + system instruction
OUTPUT_TOKENS_PER_MINUTE = 800  # transcribed text output

# Models displayed in the TUI chooser, in display order.
# Maps display key → (model_id, emoji, label)
MODEL_MENU = [
    ("gemini-3.5-flash", "🟢", "Flash", "fast, balanced (default)"),
    ("gemini-3.1-flash-lite-preview", "🟡", "Flash-Lite", "cheapest, lower quality"),
    ("gemini-3.1-pro-preview", "🔴", "Pro", "premium, expensive"),
]


class ModelPricing(TypedDict):
    input: float  # USD per 1M input tokens
    output: float  # USD per 1M output tokens
    cache: float  # USD per 1M cached tokens


def _estimate_cost_per_minute(rates: ModelPricing) -> float:
    """Estimate transcription cost per minute of audio/video.

    Uses heuristic token counts:
      - 1500 input tokens per minute (prompt + system instruction)
      - 800 output tokens per minute (transcribed text)
    """
    return (INPUT_TOKENS_PER_MINUTE / 1_000_000) * rates["input"] + (
        OUTPUT_TOKENS_PER_MINUTE / 1_000_000
    ) * rates["output"]


def fetch_pricing(timeout: float = PRICETOKEN_TIMEOUT) -> dict[str, ModelPricing]:
    """Fetch pricing from PriceToken API and merge with hardcoded fallback.

    Returns a dict keyed by model ID with input/output/cache rates.
    On any failure (network, timeout, parse error), returns FALLBACK_PRICING
    unchanged. Cache rates always come from FALLBACK_PRICING since PriceToken
    does not provide them.

    Args:
        timeout: HTTP request timeout in seconds (default: 2.0).

    Returns:
        Merged pricing dict. PriceToken values preferred for input/output
        rates; FALLBACK_PRICING always used for cache rates and as fallback
        for models not in PriceToken.
    """
    # Start with a copy of fallback
    merged: dict[str, ModelPricing] = {k: dict(v) for k, v in FALLBACK_PRICING.items()}

    try:
        req = urllib.request.Request(  # noqa: S310
            PRICETOKEN_URL,
            headers={"Accept": "application/json", "User-Agent": "agent-ear/1.1"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
            data = json.loads(resp.read().decode())

        models = data.get("data", [])
        if not isinstance(models, list):
            return merged

        for model in models:
            model_id = model.get("modelId", "")
            if not model_id:
                continue

            input_rate = model.get("inputPerMTok")
            output_rate = model.get("outputPerMTok")
            if input_rate is None or output_rate is None:
                continue

            # Use fallback cache rate if we have one, else default 10% of input
            fallback = FALLBACK_PRICING.get(model_id, {})
            cache_rate = fallback.get("cache", input_rate * 0.1)

            merged[model_id] = ModelPricing(
                input=float(input_rate),
                output=float(output_rate),
                cache=float(cache_rate),
            )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        # Graceful degradation: return fallback on any error
        pass

    return merged


def format_model_menu(pricing: dict[str, ModelPricing]) -> list[str]:
    """Return gum-formatted menu strings with $/min of transcription.

    Output format per line:
      "🟢 Flash — ~$0.0095/min  (fast, balanced)"
      "🟡 Flash-Lite — ~$0.0016/min  (cheapest, lower quality)"
      "🔴 Pro — ~$0.0126/min  (premium, expensive)"

    Args:
        pricing: Dict of model ID → ModelPricing (from fetch_pricing()).

    Returns:
        List of formatted strings suitable for gum choose.
    """
    lines = []
    for model_id, emoji, label, description in MODEL_MENU:
        rates = pricing.get(model_id, FALLBACK_PRICING.get(model_id, {}))
        if rates:
            cpm = _estimate_cost_per_minute(rates)
            lines.append(f"{emoji} {label} — ~${cpm:.4f}/min  ({description})")
        else:
            lines.append(f"{emoji} {label} — pricing unavailable  ({description})")
    return lines


def get_rates(model: str, cache_path: str | None = None) -> ModelPricing:
    """Get pricing rates for a model.

    Resolution order:
      1. Read from cache_path (temp file written by --fetch-pricing)
      2. Fall back to FALLBACK_PRICING

    Args:
        model: Model ID (e.g. "gemini-3.5-flash").
        cache_path: Optional path to JSON pricing cache file.

    Returns:
        ModelPricing dict with input/output/cache rates.
        Falls back to gemini-3.5-flash rates if model is unknown.
    """
    default = FALLBACK_PRICING.get("gemini-3.5-flash", {"input": 1.50, "output": 9.00, "cache": 0.15})

    if cache_path:
        try:
            with open(cache_path) as f:
                cached_pricing = json.load(f)
            rates = cached_pricing.get(model)
            if rates and "input" in rates and "output" in rates:
                return ModelPricing(
                    input=float(rates["input"]),
                    output=float(rates["output"]),
                    cache=float(rates.get("cache", rates["input"] * 0.1)),
                )
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError):
            pass

    return FALLBACK_PRICING.get(model, default)


def write_pricing_cache(pricing: dict[str, ModelPricing]) -> str:
    """Write pricing dict to a temp file and return the path.

    The file is written to $TMPDIR/agent-ear-pricing-<pid>.json.
    Caller is responsible for cleanup (or OS handles it on reboot).

    Returns:
        Absolute path to the written cache file.
    """
    cache_dir = tempfile.gettempdir()
    cache_path = os.path.join(cache_dir, f"agent-ear-pricing-{os.getpid()}.json")
    with open(cache_path, "w") as f:
        json.dump(pricing, f)
    return cache_path


def cli_fetch_pricing():
    """CLI entrypoint for --fetch-pricing.

    Fetches pricing, writes cache file, prints formatted gum menu to stdout,
    prints cache path to stderr (for shell to capture).
    """
    pricing = fetch_pricing()
    cache_path = write_pricing_cache(pricing)

    # Print cache path to stderr so shell can capture it
    print(f"PRICETOKEN_CACHE={cache_path}", file=sys.stderr)

    # Print formatted gum menu items to stdout
    for line in format_model_menu(pricing):
        print(line)
