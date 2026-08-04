import anthropic

from ..errors import ProviderError
from ..models import LLMRequest, LLMResponse, Usage
from ..provider import Provider


class ClaudeProvider(Provider):
    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = await self._client.messages.create(
                model=request.model,
                system=request.system or anthropic.NOT_GIVEN,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except anthropic.APIError as exc:
            raise ProviderError(f"Claude API error: {exc}") from exc

        content = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            content=content,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )
