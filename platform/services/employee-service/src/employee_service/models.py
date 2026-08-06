import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import TenantScopedBase

# Native array on Postgres; falls back to generic JSON (e.g. sqlite) in tests.
RolesVariant = JSON().with_variant(ARRAY(String), "postgresql")


class Employee(TenantScopedBase):
    __tablename__ = "employees"
    __table_args__ = (
        # Required so manager_id can FK back into (tenant_id, employee_id) below —
        # guarantees at the DB level that a manager is always in the same tenant.
        UniqueConstraint("tenant_id", "employee_id", name="uq_employees_tenant_employee"),
        UniqueConstraint("tenant_id", "email", name="uq_employees_tenant_email"),
        ForeignKeyConstraint(
            ["tenant_id", "manager_id"],
            ["employees.tenant_id", "employees.employee_id"],
            name="fk_employees_manager_same_tenant",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department: Mapped[str | None] = mapped_column(String(255))
    designation: Mapped[str | None] = mapped_column(String(255))
    manager_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    roles: Mapped[list[str]] = mapped_column(RolesVariant, nullable=False, default=list)
    # Login access, not a soft-delete — a deactivated employee's row (and
    # audit trail, agent, memory) is untouched, auth-service just refuses
    # to issue tokens for them. Defaults true so every existing/bootstrap
    # row stays functional without a backfill.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
