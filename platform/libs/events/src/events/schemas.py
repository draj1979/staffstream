import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class LLMUsageEvent(BaseModel):
    """Emitted by LLM Gateway after every successful completion — the one
    place token/cost data is captured, per CLAUDE.md's request flow."""

    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatInteractionEvent(BaseModel):
    """Emitted by OpenClaw Runtime after every /chat call, success or
    failure — this is where conversation count, error rate, and latency
    come from; LLMUsageEvent alone can't tell you a call failed before
    ever reaching the LLM."""

    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    success: bool
    error_stage: str | None = None  # "agent" | "memory" | "knowledge" | "employee" | "llm" | None
    latency_ms: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillUsageEvent(BaseModel):
    """Schema defined ahead of Phase 8's Skill Marketplace so Analytics
    Service doesn't need another migration when it lands — no producer
    emits this yet, since no skill execution mechanism exists in OpenClaw
    yet (Agent.skills is just a name list today)."""

    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    skill_name: str
    success: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
