from llm_gateway.pricing import estimate_cost_usd


def test_gemini_2_5_flash_lite_uses_its_own_rate_not_the_default_fallback():
    # $0.10/M input, $0.40/M output — distinct from DEFAULT_PRICING's
    # Claude Sonnet-tier rates ($3.00/$15.00), so this only passes if the
    # model has its own table entry rather than silently falling back.
    cost = estimate_cost_usd("gemini-2.5-flash-lite", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.50


def test_gemini_flash_lite_latest_uses_its_own_rate_not_the_default_fallback():
    # The alias actually returned by Google's API for API keys that can't
    # reach the dated gemini-2.5-flash-lite id anymore (see this file's
    # comment) — same rate, but needs its own table entry since pricing
    # is keyed by the literal model string.
    cost = estimate_cost_usd("gemini-flash-lite-latest", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.50


def test_unknown_model_falls_back_to_default_pricing():
    cost = estimate_cost_usd("some-future-model-id", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 18.0  # DEFAULT_PRICING: $3.00 in + $15.00 out
