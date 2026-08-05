import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    # Python-side default, not server_default=func.now() — same reasoning
    # as every other service: SQLite's CURRENT_TIMESTAMP is only
    # second-resolution, which breaks append-order in fast test loops.
    return datetime.now(UTC)


class AuditLogEntry(TenantScopedBase):
    """One row per state-changing action across the platform. Deliberately
    has no update/delete route anywhere in this service (see routers/audit.py)
    — an audit trail that can be edited after the fact isn't one. A real
    deployment should back this with a DB role that's only ever granted
    INSERT + SELECT on this table, so the immutability guarantee doesn't
    rest on "nobody wrote the route" alone.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(255), index=True)
    entry_metadata: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
