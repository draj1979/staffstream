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

OpenClaw Runtime's tool-calling loop builds every follow-up message in
Anthropic's content-block shape (`tool_use`/`tool_result` blocks) — that
shape is baked into runtime.py regardless of which provider is actually
serving the request, since Runtime has no per-provider branch of its
own. `_to_openai_messages` below is what makes that a valid *continuing*
conversation for this class's providers too, not just the first turn:
an assistant `tool_use` block becomes OpenAI's message-level `tool_calls`
field, and each `tool_result` block becomes its own `role: "tool"`
message keyed by `tool_call_id` — neither of which exists in Anthropic's
shape, and both of which OpenAI's wire format requires instead of it.
"""

import json

import httpx

from ..errors import ProviderError
from ..models import LLMRequest, LLMResponse, Message, ToolCall, Usage
from ..provider import Provider


def _to_openai_messages(system: str | None, messages: list[Message]) -> list[dict]:
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})

    for m in messages:
        if isinstance(m.content, str):
            out.append({"role": m.role, "content": m.content})
            continue

        # list[dict] of Anthropic content blocks (text / tool_use /
        # tool_result) — only ever appears on the assistant's own
        # tool_use echo-back and the user-role tool_result turn that
        # follows it; see runtime.py's _run_tool_calling_loop.
        if m.role == "assistant":
            text = "".join(b["text"] for b in m.content if b.get("type") == "text")
            tool_use_blocks = [b for b in m.content if b.get("type") == "tool_use"]
            assistant_msg: dict = {"role": "assistant", "content": text or None}
            if tool_use_blocks:
                assistant_msg["tool_calls"] = [
                    {
                        "id": b["id"],
                        "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                    }
                    for b in tool_use_blocks
                ]
            out.append(assistant_msg)
            continue

        # user role: one OpenAI "tool" message per tool_result block —
        # OpenAI has no equivalent of Anthropic bundling several results
        # into one user-role message's content list, each is its own
        # top-level message instead.
        for b in m.content:
            if b.get("type") == "tool_result":
                out.append(
                    {"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]}
                )
            elif b.get("type") == "text":
                out.append({"role": "user", "content": b["text"]})

    return out


class OpenAICompatibleProvider(Provider):
    def __init__(self, *, base_url: str, api_key: str, display_name: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=60.0)
        self._api_key = api_key
        self._display_name = display_name

    async def complete(self, request: LLMRequest) -> LLMResponse:
        messages = _to_openai_messages(request.system, request.messages)

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
