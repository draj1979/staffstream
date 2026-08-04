import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base. Use directly only for tables that are NOT
    tenant-scoped (e.g. the Tenant table itself, which is the root entity)."""


class TenantScopedBase(Base):
    """Abstract base for every tenant-scoped table.

    Every subclass gets an indexed, non-nullable tenant_id column. The
    session listener registered in `tenancy.session` enforces
    `WHERE tenant_id = :current_tenant` on every SELECT/UPDATE/DELETE against
    subclasses of this base, and stamps/validates tenant_id on INSERT — so a
    hand-written query against a tenant-scoped table literally cannot forget
    the filter. Any table holding tenant data MUST inherit from this class
    rather than `Base` directly.
    """

    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
