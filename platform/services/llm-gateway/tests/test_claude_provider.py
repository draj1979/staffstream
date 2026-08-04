from types import SimpleNamespace

import anthropic
import pytest
from llm_gateway.errors import ProviderError
from llm_gateway.models import LLMRequest, Message, ToolDefinition
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


async def test_claude_provider_parses_tool_use_blocks(monkeypatch):
    provider = ClaudeProvider(api_key="test-key")

    async def fake_create(**kwargs):
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="Let me check that."),
                SimpleNamespace(
                    type="tool_use",
                    id="toolu_1",
                    name="slack_post_message",
                    input={"channel_id": "C123", "text": "hi"},
                ),
            ],
            model="claude-sonnet-5",
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=20, output_tokens=10),
        )

    monkeypatch.setattr(provider._client.messages, "create", fake_create)

    request = LLMRequest(
        model="claude-sonnet-5",
        messages=[Message(role="user", content="post hi to #general")],
        tools=[
            ToolDefinition(
                name="slack_post_message",
                description="Post a message to a Slack channel",
                input_schema={"type": "object", "properties": {}},
            )
        ],
    )
    response = await provider.complete(request)

    assert response.content == "Let me check that."
    assert response.stop_reason == "tool_use"
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.id == "toolu_1"
    assert call.name == "slack_post_message"
    assert call.input == {"channel_id": "C123", "text": "hi"}


async def test_claude_provider_forwards_tools_to_anthropic(monkeypatch):
    provider = ClaudeProvider(api_key="test-key")
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_anthropic_response()

    monkeypatch.setattr(provider._client.messages, "create", fake_create)

    request = LLMRequest(
        model="claude-sonnet-5",
        messages=[Message(role="user", content="hi")],
        tools=[
            ToolDefinition(name="noop", description="does nothing", input_schema={"type": "object"})
        ],
    )
    await provider.complete(request)

    assert captured["tools"] == [
        {"name": "noop", "description": "does nothing", "input_schema": {"type": "object"}}
    ]


async def test_claude_provider_omits_tools_when_none_given(monkeypatch):
    import anthropic as anthropic_module

    provider = ClaudeProvider(api_key="test-key")
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_anthropic_response()

    monkeypatch.setattr(provider._client.messages, "create", fake_create)

    request = LLMRequest(model="claude-sonnet-5", messages=[Message(role="user", content="hi")])
    await provider.complete(request)

    assert captured["tools"] is anthropic_module.NOT_GIVEN


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
