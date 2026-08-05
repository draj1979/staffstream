"""One implementation shared by every provider below GPT itself — not a
bespoke client per vendor. OpenAI's Chat Completions wire format
(`/chat/completions`, Bearer auth, `choices[0].message`, `tool_calls`
shaped as `{id, function: {name, arguments}}`) is also what Mistral and
DeepSeek document as their own API directly, what Groq speaks for the
Llama models it hosts, and what Google publishes as an explicit
OpenAI-compatibility endpoint for Gemini
(https://ai.google.dev/gemini-api/docs/openai). Parameterizing by
base_url + api_key covers five of this phase's six providers with one
class; only Claude's native Messages API shape is different enough to
need its own (see claude.py).

Known limitation, not solved by this class: OpenClaw Runtime's Phase 8
tool-calling loop builds follow-up messages in Anthropic's content-block
shape (`tool_use`/`tool_result` blocks). That's a valid *request* to any
of these providers for the first turn (tools are translated to OpenAI's
function-calling shape below), but continuing a multi-turn tool
conversation with a non-Claude provider would need a translation layer
this phase doesn't build — OpenClaw's tool loop is Claude-only in
practice today. Flagged in the README, not silently glossed over.
"""

import json

import httpx

from ..errors import ProviderError
from ..models import LLMRequest, LLMResponse, ToolCall, Usage
from ..provider import Provider


class OpenAICompatibleProvider(Provider):
    def __init__(self, *, base_url: str, api_key: str, display_name: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=60.0)
        self._api_key = api_key
        self._display_name = display_name

    async def complete(self, request: LLMRequest) -> LLMResponse:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)

        body: dict = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]

        try:
            resp = await self._client.post(
                "/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self._display_name} API error: {exc}") from exc

        if resp.status_code >= 400:
            raise ProviderError(f"{self._display_name} API error: {resp.status_code} {resp.text}")

        data = resp.json()
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            raise ProviderError(
                f"{self._display_name} API returned an unexpected response shape: {data}"
            ) from exc

        tool_calls = [
            ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                input=json.loads(tc["function"]["arguments"] or "{}"),
            )
            for tc in (message.get("tool_calls") or [])
        ]

        usage = data.get("usage") or {}
        return LLMResponse(
            content=message.get("content") or "",
            model=data.get("model", request.model),
            stop_reason=choice.get("finish_reason"),
            usage=Usage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
            tool_calls=tool_calls,
        )
