"""create sso_connections

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sso_connections",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(length=500), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=1000), nullable=False),
        sa.Column("issuer_domain", sa.String(length=255), nullable=True),
        sa.Column("hosted_domain", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_sso_tenant_provider"),
    )
    op.create_index("ix_sso_connections_tenant_id", "sso_connections", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_sso_connections_tenant_id", table_name="sso_connections")
    op.drop_table("sso_connections")
