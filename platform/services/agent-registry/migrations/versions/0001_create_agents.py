"""create agents table

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
        "agents",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False, server_default="claude-sonnet-5"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("memory_namespace", sa.String(length=255), nullable=False),
        sa.Column("knowledge_sources", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("skills", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "employee_id", name="uq_agents_tenant_employee"),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_agents_employee_id", "agents", ["employee_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_employee_id", table_name="agents")
    op.drop_index("ix_agents_tenant_id", table_name="agents")
    op.drop_table("agents")
