"""Example per-model pricing, $ per million tokens — update these from
each vendor's actual pricing page before relying on this for real
billing. Good enough to exercise the Analytics Service's cost math end
to end, not a source of truth for what a customer should be charged.

Keyed by model name rather than (provider, model) — every vendor here
uses model IDs that are unique across the whole table in practice, and
that keeps this table (and estimate_cost_usd's call sites, which only
ever have the model string on hand) simpler than it would be with a
compound key.
"""

PRICING_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4-8": {"input": 15.0, "output": 75.0},
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-fable-5": {"input": 3.0, "output": 15.0},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    # Google Gemini
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-pro": {"input": 1.25, "output": 5.0},
    # gemini-2.5-flash-lite is still a real, listed model, but returns
    # 404 "no longer available to new users" for API keys created after
    # its cutoff — gemini-flash-lite-latest is Google's rolling alias for
    # their current flash-lite tier and what the demo tenant actually
    # runs on (see Agent Registry's per-agent model field). Kept both
    # entries: whichever one an API key can actually reach still gets
    # correctly priced.
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-flash-lite-latest": {"input": 0.10, "output": 0.40},
    # Mistral
    "mistral-large-latest": {"input": 2.0, "output": 6.0},
    "mistral-small-latest": {"input": 0.20, "output": 0.60},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # Llama (as hosted by Groq — see llm_gateway.config.llama_base_url)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
}

# Anything not in the table above (e.g. a newer model ID) still gets a
# cost estimate rather than silently reporting $0 — using Claude
# Sonnet-tier rates as the fallback, since that's the most commonly used
# tier across this platform.
DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


def estimate_cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING_PER_MILLION_TOKENS.get(model, DEFAULT_PRICING)
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
