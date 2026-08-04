from abc import ABC, abstractmethod

from .models import LLMRequest, LLMResponse


class Provider(ABC):
    """The contract every LLM provider implements. Phase 10 adds GPT,
    Gemini, Llama, Mistral, DeepSeek, local — each is just another class
    implementing this method and registered with the gateway under its own
    name; nothing else in the gateway (or its callers) changes."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
