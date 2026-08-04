from .errors import UnknownProviderError
from .models import LLMRequest, LLMResponse
from .provider import Provider
from .providers.claude import ClaudeProvider


class LLMGateway:
    """Dispatches a completion request to the named provider. Only "claude"
    is registered for Phase 3 — Phase 10 registers the rest."""

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


def build_default_gateway(*, anthropic_api_key: str) -> LLMGateway:
    gateway = LLMGateway()
    gateway.register_provider("claude", ClaudeProvider(api_key=anthropic_api_key))
    return gateway
