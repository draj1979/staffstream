"""Example per-model pricing, $ per million tokens — update these from
Anthropic's actual pricing page before relying on this for real billing.
Good enough to exercise the Analytics Service's cost math end-to-end, not
a source of truth for what a customer should be charged.
"""

PRICING_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "claude-opus-4-8": {"input": 15.0, "output": 75.0},
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-fable-5": {"input": 3.0, "output": 15.0},
}

# Anything not in the table above (e.g. a newer model ID) still gets a
# cost estimate rather than silently reporting $0 — using Sonnet-tier
# rates as the fallback, since that's the most commonly used tier.
DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


def estimate_cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING_PER_MILLION_TOKENS.get(model, DEFAULT_PRICING)
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
