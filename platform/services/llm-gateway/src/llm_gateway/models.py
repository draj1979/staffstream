from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class LLMRequest(BaseModel):
    model: str
    messages: list[Message]
    system: str | None = None
    temperature: float = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, gt=0)


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    content: str
    model: str
    stop_reason: str | None
    usage: Usage
