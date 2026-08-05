import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase

# Native JSONB on Postgres; falls back to generic JSON (e.g. sqlite) in tests.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Agent(TenantScopedBase):
    """One agent profile per employee. employee_id is unique per tenant —
    enforced both here (app-level check in crud.py) and at the DB level via
    the composite unique constraint below."""

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_agents_tenant_employee"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    personality: Mapped[str | None] = mapped_column(Text)
    # Which LLM Gateway provider this agent's calls go through — Phase 10
    # adds five more providers alongside Claude (see llm-gateway). Set
    # from the tenant's own llm_config default at agent-creation time
    # (see employee_service.agent_registry_client), overridable per agent
    # after that.
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="claude")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-5")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    memory_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_sources: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    skills: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    permissions: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
