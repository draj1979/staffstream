"""create tenants table

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

subscription_status = postgresql.ENUM(
    "trial", "active", "past_due", "canceled", name="subscription_status", create_type=False
)


def upgrade() -> None:
    subscription_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("llm_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("branding", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "subscription_status",
            subscription_status,
            nullable=False,
            server_default="trial",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tenants")
    subscription_status.drop(op.get_bind(), checkfirst=True)
