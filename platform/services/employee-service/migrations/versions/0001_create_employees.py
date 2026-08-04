"""create employees table

Revision ID: 0001
Revises:
Create Date: 2026-08-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("designation", sa.String(length=255), nullable=True),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("roles", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "employee_id", name="uq_employees_tenant_employee"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_employees_tenant_email"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "manager_id"],
            ["employees.tenant_id", "employees.employee_id"],
            name="fk_employees_manager_same_tenant",
        ),
    )
    op.create_index("ix_employees_tenant_id", "employees", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_employees_tenant_id", table_name="employees")
    op.drop_table("employees")
