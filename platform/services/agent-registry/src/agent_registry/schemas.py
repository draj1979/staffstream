import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    employee_id: uuid.UUID
    name: str = "Personal Assistant"
    personality: str | None = None
    model: str = "claude-sonnet-5"
    temperature: float = Field(default=1.0, ge=0.0, le=1.0)
    prompt: str = "You are a helpful personal assistant for this employee."
    memory_namespace: str | None = None
    knowledge_sources: list[str] = []
    skills: list[str] = []
    permissions: list[str] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    personality: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    prompt: str | None = None
    knowledge_sources: list[str] | None = None
    skills: list[str] | None = None
    permissions: list[str] | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    name: str
    personality: str | None
    model: str
    temperature: float
    prompt: str
    memory_namespace: str
    knowledge_sources: list[str]
    skills: list[str]
    permissions: list[str]
    created_at: datetime
    updated_at: datetime
