"""create skill marketplace tables: skills, tenant_skill_enablement, employee_connections

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOG = [
    {
        "skill_id": "slack",
        "name": "Slack",
        "description": "Read and post to Slack channels the employee belongs to.",
        "connector": "slack",
    },
    {
        "skill_id": "google_calendar",
        "name": "Google Calendar",
        "description": "Read and create events on the employee's own Google Calendar.",
        "connector": "google_calendar",
    },
]


def upgrade() -> None:
    skills = op.create_table(
        "skills",
        sa.Column("skill_id", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("connector", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.bulk_insert(skills, _CATALOG)

    op.create_table(
        "tenant_skill_enablement",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("skill_id", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "skill_id", name="uq_tenant_skill_enablement"),
    )
    op.create_index(
        "ix_tenant_skill_enablement_tenant_id", "tenant_skill_enablement", ["tenant_id"]
    )
    op.create_index(
        "ix_tenant_skill_enablement_skill_id", "tenant_skill_enablement", ["skill_id"]
    )

    op.create_table(
        "employee_connections",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=100), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_scope", sa.String(length=500), nullable=True),
        sa.Column("external_account", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "employee_id", "skill_id", name="uq_employee_connection"
        ),
    )
    op.create_index("ix_employee_connections_tenant_id", "employee_connections", ["tenant_id"])
    op.create_index(
        "ix_employee_connections_employee_id", "employee_connections", ["employee_id"]
    )
    op.create_index("ix_employee_connections_skill_id", "employee_connections", ["skill_id"])


def downgrade() -> None:
    op.drop_index("ix_employee_connections_skill_id", table_name="employee_connections")
    op.drop_index("ix_employee_connections_employee_id", table_name="employee_connections")
    op.drop_index("ix_employee_connections_tenant_id", table_name="employee_connections")
    op.drop_table("employee_connections")

    op.drop_index("ix_tenant_skill_enablement_skill_id", table_name="tenant_skill_enablement")
    op.drop_index("ix_tenant_skill_enablement_tenant_id", table_name="tenant_skill_enablement")
    op.drop_table("tenant_skill_enablement")

    op.drop_table("skills")
