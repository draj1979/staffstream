import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    reply: str
    agent_id: uuid.UUID
    model: str
    usage: Usage
