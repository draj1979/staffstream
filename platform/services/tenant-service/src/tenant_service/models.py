import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import Base

# Native JSONB on Postgres; falls back to generic JSON (e.g. sqlite) in tests.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class SubscriptionStatus(enum.StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class Tenant(Base):
    """The root entity — a tenant is not itself tenant-scoped, it *is* the
    tenant. Every other table in the platform hangs off this table's id via
    tenant_id (see tenancy.TenantScopedBase)."""

    __tablename__ = "tenants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    storage_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    llm_config: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    branding: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
