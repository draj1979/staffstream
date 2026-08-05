from .errors import UnknownProviderError
from .models import LLMRequest, LLMResponse
from .provider import Provider
from .providers.claude import ClaudeProvider
from .providers.openai_compatible import OpenAICompatibleProvider


class LLMGateway:
    """Dispatches a completion request to the named provider — six
    registered as of Phase 10 (Claude natively, five more via the shared
    OpenAICompatibleProvider), each just another entry in this dict.
    Nothing about the gateway or its callers changes as providers are
    added or removed."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register_provider(self, name: str, provider: Provider) -> None:
        self._providers[name] = provider

    async def complete(self, provider: str, request: LLMRequest) -> LLMResponse:
        if provider not in self._providers:
            raise UnknownProviderError(
                f"Unknown provider {provider!r}; registered: {sorted(self._providers)}"
            )
        return await self._providers[provider].complete(request)


def build_default_gateway(
    *,
    anthropic_api_key: str,
    openai_api_key: str,
    openai_base_url: str,
    gemini_api_key: str,
    gemini_base_url: str,
    mistral_api_key: str,
    mistral_base_url: str,
    deepseek_api_key: str,
    deepseek_base_url: str,
    llama_api_key: str,
    llama_base_url: str,
) -> LLMGateway:
    gateway = LLMGateway()
    gateway.register_provider("claude", ClaudeProvider(api_key=anthropic_api_key))
    gateway.register_provider(
        "openai",
        OpenAICompatibleProvider(
            base_url=openai_base_url, api_key=openai_api_key, display_name="OpenAI"
        ),
    )
    gateway.register_provider(
        "gemini",
        OpenAICompatibleProvider(
            base_url=gemini_base_url, api_key=gemini_api_key, display_name="Gemini"
        ),
    )
    gateway.register_provider(
        "mistral",
        OpenAICompatibleProvider(
            base_url=mistral_base_url, api_key=mistral_api_key, display_name="Mistral"
        ),
    )
    gateway.register_provider(
        "deepseek",
        OpenAICompatibleProvider(
            base_url=deepseek_base_url, api_key=deepseek_api_key, display_name="DeepSeek"
        ),
    )
    gateway.register_provider(
        "llama",
        OpenAICompatibleProvider(
            base_url=llama_base_url, api_key=llama_api_key, display_name="Llama"
        ),
    )
    return gateway
