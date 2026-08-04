from types import SimpleNamespace

import anthropic
import pytest
from llm_gateway.errors import ProviderError
from llm_gateway.models import LLMRequest, Message
from llm_gateway.providers.claude import ClaudeProvider


def _fake_anthropic_response():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Hello, human.")],
        model="claude-sonnet-5",
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=12, output_tokens=4),
    )


async def test_claude_provider_maps_request_and_response(monkeypatch):
    provider = ClaudeProvider(api_key="test-key")

    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_anthropic_response()

    monkeypatch.setattr(provider._client.messages, "create", fake_create)

    request = LLMRequest(
        model="claude-sonnet-5",
        system="Be terse.",
        messages=[Message(role="user", content="hi")],
        temperature=0.3,
        max_tokens=256,
    )
    response = await provider.complete(request)

    assert response.content == "Hello, human."
    assert response.model == "claude-sonnet-5"
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 4

    assert captured["model"] == "claude-sonnet-5"
    assert captured["system"] == "Be terse."
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 256


async def test_claude_provider_wraps_api_errors(monkeypatch):
    provider = ClaudeProvider(api_key="test-key")

    async def fake_create(**kwargs):
        raise anthropic.APIError(
            "boom", request=SimpleNamespace(), body=None
        )

    monkeypatch.setattr(provider._client.messages, "create", fake_create)

    request = LLMRequest(model="claude-sonnet-5", messages=[Message(role="user", content="hi")])
    with pytest.raises(ProviderError):
        await provider.complete(request)
