import pytest
from llm_gateway.errors import UnknownProviderError
from llm_gateway.gateway import LLMGateway
from llm_gateway.models import LLMRequest, LLMResponse, Message, Usage
from llm_gateway.provider import Provider


class FakeProvider(Provider):
    def __init__(self, reply: str = "hello"):
        self.reply = reply
        self.received: LLMRequest | None = None

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.received = request
        return LLMResponse(
            content=self.reply,
            model=request.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=1, output_tokens=1),
        )


def _request() -> LLMRequest:
    return LLMRequest(model="claude-sonnet-5", messages=[Message(role="user", content="hi")])


async def test_gateway_dispatches_to_registered_provider():
    gateway = LLMGateway()
    fake = FakeProvider(reply="hi there")
    gateway.register_provider("fake", fake)

    response = await gateway.complete("fake", _request())

    assert response.content == "hi there"
    assert fake.received is not None
    assert fake.received.messages[0].content == "hi"


async def test_gateway_rejects_unknown_provider():
    gateway = LLMGateway()
    gateway.register_provider("fake", FakeProvider())

    with pytest.raises(UnknownProviderError):
        await gateway.complete("nonexistent", _request())


def _default_gateway_kwargs() -> dict:
    return {
        "anthropic_api_key": "test-key",
        "openai_api_key": "test-key",
        "openai_base_url": "https://api.openai.com/v1",
        "gemini_api_key": "test-key",
        "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "mistral_api_key": "test-key",
        "mistral_base_url": "https://api.mistral.ai/v1",
        "deepseek_api_key": "test-key",
        "deepseek_base_url": "https://api.deepseek.com",
        "llama_api_key": "test-key",
        "llama_base_url": "https://api.groq.com/openai/v1",
    }


async def test_build_default_gateway_registers_all_six_providers():
    from llm_gateway.gateway import build_default_gateway

    gateway = build_default_gateway(**_default_gateway_kwargs())
    with pytest.raises(UnknownProviderError):
        await gateway.complete("nonexistent", _request())
    # Confirmed indirectly: each is registered (a real call would need
    # network/API keys, which this test deliberately doesn't exercise).
    assert set(gateway._providers) == {
        "claude",
        "openai",
        "gemini",
        "mistral",
        "deepseek",
        "llama",
    }
