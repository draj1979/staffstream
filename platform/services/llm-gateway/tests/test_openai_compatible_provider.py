import json

import httpx
import pytest
from llm_gateway.errors import ProviderError
from llm_gateway.models import LLMRequest, Message, ToolDefinition
from llm_gateway.providers.openai_compatible import OpenAICompatibleProvider


def _provider(handler) -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1", api_key="test-key", display_name="TestVendor"
    )
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/v1", transport=httpx.MockTransport(handler)
    )
    return provider


async def test_maps_request_and_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Hello, human."}, "finish_reason": "stop"}
                ],
                "model": "gpt-4o",
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    provider = _provider(handler)
    request = LLMRequest(
        model="gpt-4o",
        system="Be terse.",
        messages=[Message(role="user", content="hi")],
        temperature=0.3,
        max_tokens=256,
    )
    response = await provider.complete(request)

    assert response.content == "Hello, human."
    assert response.model == "gpt-4o"
    assert response.stop_reason == "stop"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 4

    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "gpt-4o"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "Be terse."}
    assert captured["body"]["messages"][1] == {"role": "user", "content": "hi"}
    assert captured["body"]["temperature"] == 0.3
    assert captured["body"]["max_tokens"] == 256


async def test_parses_tool_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "slack_post_message",
                                        "arguments": json.dumps(
                                            {"channel_id": "C1", "text": "hi"}
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "model": "gpt-4o",
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    provider = _provider(handler)
    request = LLMRequest(
        model="gpt-4o",
        messages=[Message(role="user", content="post hi to #general")],
        tools=[
            ToolDefinition(
                name="slack_post_message",
                description="Post a message",
                input_schema={"type": "object", "properties": {}},
            )
        ],
    )
    response = await provider.complete(request)

    assert response.content == ""
    assert response.stop_reason == "tool_calls"
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "slack_post_message"
    assert call.input == {"channel_id": "C1", "text": "hi"}


async def test_forwards_tools_in_openai_function_shape():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "model": "gpt-4o",
                "usage": {},
            },
        )

    provider = _provider(handler)
    request = LLMRequest(
        model="gpt-4o",
        messages=[Message(role="user", content="hi")],
        tools=[
            ToolDefinition(
                name="noop", description="does nothing", input_schema={"type": "object"}
            )
        ],
    )
    await provider.complete(request)

    assert captured["body"]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "noop",
                "description": "does nothing",
                "parameters": {"type": "object"},
            },
        }
    ]


async def test_missing_usage_fields_default_to_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]},
        )

    provider = _provider(handler)
    request = LLMRequest(model="gpt-4o", messages=[Message(role="user", content="hi")])
    response = await provider.complete(request)

    assert response.usage.input_tokens == 0
    assert response.usage.output_tokens == 0


async def test_raises_provider_error_on_http_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    provider = _provider(handler)
    request = LLMRequest(model="gpt-4o", messages=[Message(role="user", content="hi")])
    with pytest.raises(ProviderError, match="401"):
        await provider.complete(request)


async def test_raises_provider_error_on_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = _provider(handler)
    request = LLMRequest(model="gpt-4o", messages=[Message(role="user", content="hi")])
    with pytest.raises(ProviderError):
        await provider.complete(request)


async def test_raises_provider_error_on_transport_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = _provider(handler)
    request = LLMRequest(model="gpt-4o", messages=[Message(role="user", content="hi")])
    with pytest.raises(ProviderError):
        await provider.complete(request)
