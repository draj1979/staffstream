import anthropic

from ..errors import ProviderError
from ..models import LLMRequest, LLMResponse, ToolCall, Usage
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
                tools=(
                    [t.model_dump() for t in request.tools]
                    if request.tools
                    else anthropic.NOT_GIVEN
                ),
            )
        except anthropic.APIError as exc:
            raise ProviderError(f"Claude API error: {exc}") from exc

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return LLMResponse(
            content="".join(text_parts),
            model=response.model,
            stop_reason=response.stop_reason,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            tool_calls=tool_calls,
        )
