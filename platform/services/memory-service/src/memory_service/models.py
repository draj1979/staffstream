import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase

# Native JSONB on Postgres; falls back to generic JSON (e.g. sqlite) in tests.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    # Python-side (not server_default=func.now()) deliberately: SQLite's
    # CURRENT_TIMESTAMP only has second resolution, which ties-breaks
    # append-order incorrectly for rapid successive inserts (e.g. a fast
    # test loop). datetime.now() has microsecond resolution on every
    # backend, so ORDER BY created_at is actually append-ordered.
    return datetime.now(UTC)


class ConversationTurn(TenantScopedBase):
    """One message in a conversation — append-only log, ordered by
    created_at. memory_namespace is the actual partition key (matches the
    owning Agent's memory_namespace); tenant_id still goes through the
    standard tenancy filter on every query, same as every other table."""

    __tablename__ = "conversation_turns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    memory_namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LongTermMemoryEntry(TenantScopedBase):
    """Durable notes about an employee that should persist well beyond a
    single conversation (e.g. a summarized fact worth remembering)."""

    __tablename__ = "long_term_memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    memory_namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Preference(TenantScopedBase):
    """Key/value settings for an employee (e.g. tone, language). One row
    per key per namespace — set() upserts by (tenant_id, memory_namespace, key)."""

    __tablename__ = "preferences"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "memory_namespace", "key", name="uq_preferences_namespace_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    memory_namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict | list | str | int | float | bool] = mapped_column(
        JSONVariant, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class LearnedFact(TenantScopedBase):
    """Something OpenClaw has learned about the employee's behaviour or
    context — distinct from long-term memory only in intent, not shape;
    kept as its own table so it can evolve independently (e.g. confidence
    scoring) without touching long-term memory's schema."""

    __tablename__ = "learned_facts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    memory_namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
