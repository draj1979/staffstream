import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, Uuid, func
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


class SsoConnection(TenantScopedBase):
    """One tenant's own IdP configuration for one provider — "each tenant
    configures their own IdP", not a platform-wide credential. Both
    Google Workspace and Auth0 are OIDC-compliant, so this one table (and
    the generic oidc.py helper) covers both; client_secret is Fernet-
    encrypted at rest, same reasoning as Skill Marketplace's OAuth tokens.
    """

    __tablename__ = "sso_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", name="uq_sso_tenant_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # "google_workspace" | "auth0"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[str] = mapped_column(String(500), nullable=False)
    client_secret_encrypted: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Auth0 needs its tenant domain to build the discovery URL
    # (https://{issuer_domain}/.well-known/openid-configuration); Google's
    # issuer is fixed, so this stays unused for that provider.
    issuer_domain: Mapped[str | None] = mapped_column(String(255))
    # Google Workspace only: restrict SSO logins to a single Workspace
    # domain, checked against the id_token's `hd` claim.
    hosted_domain: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
