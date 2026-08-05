import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import Base, TenantScopedBase

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    # Python-side default, not server_default=func.now() — same reasoning
    # as every other service: SQLite's CURRENT_TIMESTAMP is only
    # second-resolution, which breaks ordering in fast test loops.
    return datetime.now(UTC)


class Skill(Base):
    """The registry of available skills — a shared catalog across every
    tenant, not tenant-scoped. Which tenants have actually turned a skill
    on lives in TenantSkillEnablement below; a row existing here just
    means the platform knows how to run it."""

    __tablename__ = "skills"

    skill_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    connector: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TenantSkillEnablement(TenantScopedBase):
    """Opt-in per tenant — a skill existing in the catalog above never
    makes it usable on its own. A tenant admin has to flip this on first,
    and an individual agent still needs the skill in its own `skills`
    allowlist (Agent Registry) before OpenClaw offers it to that
    employee's LLM calls."""

    __tablename__ = "tenant_skill_enablement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "skill_id", name="uq_tenant_skill_enablement"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class EmployeeConnection(TenantScopedBase):
    """One employee's own OAuth grant for one skill/connector — never
    shared across employees, even within the same tenant. Every
    Slack/Calendar call a skill makes on this employee's behalf uses only
    the token stored here, so it can never act beyond what this specific
    employee authorized (see crypto.py for the at-rest encryption)."""

    __tablename__ = "employee_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "skill_id", name="uq_employee_connection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_scope: Mapped[str | None] = mapped_column(String(500))
    # Human-readable identity at the provider (Slack user id, Google
    # account email, ...) — display only, never used for authorization.
    external_account: Mapped[str | None] = mapped_column(String(255))
    # Whatever else the OAuth exchange handed back that a connector needs
    # on every later call — Salesforce's instance_url, Jira's cloudId,
    # ... (see connectors/base.py's TokenSet.extra). Empty for connectors
    # that don't need any (Slack, Google Calendar).
    connection_metadata: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
