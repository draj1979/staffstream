import enum
import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase

EMBEDDING_DIMENSION = 512  # voyage-3-lite


def _utcnow() -> datetime:
    return datetime.now(UTC)


class KnowledgeScope(enum.StrEnum):
    COMPANY = "company"
    DEPARTMENT = "department"
    PERSONAL = "personal"


class DocumentStatus(enum.StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# Shared Enum instances so SQLAlchemy emits a single Postgres ENUM type and
# reuses it across both tables, rather than trying to CREATE TYPE twice.
# values_callable is required — without it SQLAlchemy persists the
# member .name (e.g. "COMPANY") instead of .value ("company"), which
# doesn't match what these enums' string values actually need to look
# like in the DB (see tenant-service's SubscriptionStatus for the same fix).
_knowledge_scope_enum = Enum(
    KnowledgeScope, name="knowledge_scope", values_callable=lambda e: [m.value for m in e]
)
_document_status_enum = Enum(
    DocumentStatus, name="document_status", values_callable=lambda e: [m.value for m in e]
)


class Document(TenantScopedBase):
    """A single uploaded file. scope determines which of department /
    employee_id is populated — enforced in the API layer, not the DB,
    same as Agent's employee_id/tenant_id relationship."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scope: Mapped[KnowledgeScope] = mapped_column(_knowledge_scope_enum, nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    uploaded_by_employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        _document_status_enum, nullable=False, default=DocumentStatus.PROCESSING
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Chunk(TenantScopedBase):
    """One embedded slice of a Document's extracted text. scope/department/
    employee_id are denormalized from the parent Document so retrieval can
    filter by visibility without a join on the hot path."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[KnowledgeScope] = mapped_column(_knowledge_scope_enum, nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
