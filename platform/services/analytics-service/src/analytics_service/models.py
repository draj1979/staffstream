import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase


def _utcnow() -> datetime:
    # Python-side (not server_default=func.now()) deliberately: SQLite's
    # CURRENT_TIMESTAMP only has second resolution, which breaks
    # chronological ordering for rapid successive inserts (e.g. tests, or
    # a burst of real traffic). datetime.now() has microsecond resolution
    # on every backend — see memory-service for the same fix.
    return datetime.now(UTC)


class LLMUsageEventRow(TenantScopedBase):
    """One row per LLMUsageEvent ingested from the queue — captured at the
    LLM Gateway boundary, per CLAUDE.md's request flow."""

    __tablename__ = "llm_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class ChatInteractionEventRow(TenantScopedBase):
    """One row per ChatInteractionEvent ingested from the queue — every
    /chat call, success or failure. This is where conversation count,
    error rate, and latency come from."""

    __tablename__ = "chat_interaction_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_stage: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class SkillUsageEventRow(TenantScopedBase):
    """Schema ready ahead of Phase 8's Skill Marketplace — no producer
    ingests into this yet, since no skill execution mechanism exists in
    OpenClaw yet. Kept here (rather than added later) so Phase 8 doesn't
    need another migration just to start emitting."""

    __tablename__ = "skill_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
