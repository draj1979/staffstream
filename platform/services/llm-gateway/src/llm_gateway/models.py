from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # "user" | "assistant"
    # A plain string for ordinary turns; a list of raw Anthropic content
    # blocks (tool_use / tool_result / text dicts) for the follow-up turns
    # of a tool-calling exchange. Provider-specific shape, same as `tools`
    # below — Phase 10's multi-provider abstraction will need to normalize
    # this; not worth generalizing before there's a second provider to
    # generalize against.
    content: str | list[dict]


class ToolDefinition(BaseModel):
    """One callable tool exposed to the model, Anthropic tool-schema shape
    (name/description/JSON-schema input) — what OpenClaw Runtime builds
    from Skill Marketplace's tool catalog before every /generate call."""

    name: str
    description: str
    input_schema: dict


class LLMRequest(BaseModel):
    model: str
    messages: list[Message]
    system: str | None = None
    temperature: float = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, gt=0)
    tools: list[ToolDefinition] | None = None


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ToolCall(BaseModel):
    """One tool invocation the model asked for. `id` must be echoed back
    verbatim in the corresponding tool_result block on the next turn —
    Anthropic matches results to calls by this id, not by position."""

    id: str
    name: str
    input: dict


class LLMResponse(BaseModel):
    content: str
    model: str
    stop_reason: str | None
    usage: Usage
    tool_calls: list[ToolCall] = []
