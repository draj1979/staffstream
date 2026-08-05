"""create audit_log_entries

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


def upgrade() -> None:
    op.create_table(
        "audit_log_entries",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("actor_employee_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("entry_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_entries_tenant_id", "audit_log_entries", ["tenant_id"])
    op.create_index(
        "ix_audit_log_entries_actor_employee_id", "audit_log_entries", ["actor_employee_id"]
    )
    op.create_index("ix_audit_log_entries_action", "audit_log_entries", ["action"])
    op.create_index("ix_audit_log_entries_target_type", "audit_log_entries", ["target_type"])
    op.create_index("ix_audit_log_entries_target_id", "audit_log_entries", ["target_id"])
    op.create_index("ix_audit_log_entries_created_at", "audit_log_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_entries_created_at", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_target_id", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_target_type", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_action", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_actor_employee_id", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_tenant_id", table_name="audit_log_entries")
    op.drop_table("audit_log_entries")
