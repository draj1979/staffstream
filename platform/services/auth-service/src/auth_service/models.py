import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase


class Credential(TenantScopedBase):
    """One row per employee's login credentials. employee_id doubles as the
    primary key since the relationship to Employee Service is 1:1."""

    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_credentials_tenant_email"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RefreshToken(TenantScopedBase):
    """Refresh tokens are opaque random strings handed to the client; only
    their SHA-256 hash is stored, so a DB leak doesn't hand out usable
    tokens. revoked_at is what makes logout/rotation actually revoke access
    (unlike a stateless JWT, which can't be un-issued before it expires)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
