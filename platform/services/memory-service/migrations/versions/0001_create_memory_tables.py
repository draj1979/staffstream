"""create memory tables: conversation_turns, long_term_memory_entries, preferences, learned_facts

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
        "conversation_turns",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("memory_namespace", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_turns_tenant_id", "conversation_turns", ["tenant_id"])
    op.create_index(
        "ix_conversation_turns_memory_namespace", "conversation_turns", ["memory_namespace"]
    )

    op.create_table(
        "long_term_memory_entries",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("memory_namespace", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_long_term_memory_entries_tenant_id", "long_term_memory_entries", ["tenant_id"]
    )
    op.create_index(
        "ix_long_term_memory_entries_memory_namespace",
        "long_term_memory_entries",
        ["memory_namespace"],
    )

    op.create_table(
        "preferences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("memory_namespace", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "memory_namespace", "key", name="uq_preferences_namespace_key"
        ),
    )
    op.create_index("ix_preferences_tenant_id", "preferences", ["tenant_id"])
    op.create_index("ix_preferences_memory_namespace", "preferences", ["memory_namespace"])

    op.create_table(
        "learned_facts",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("memory_namespace", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learned_facts_tenant_id", "learned_facts", ["tenant_id"])
    op.create_index("ix_learned_facts_memory_namespace", "learned_facts", ["memory_namespace"])


def downgrade() -> None:
    op.drop_index("ix_learned_facts_memory_namespace", table_name="learned_facts")
    op.drop_index("ix_learned_facts_tenant_id", table_name="learned_facts")
    op.drop_table("learned_facts")

    op.drop_index("ix_preferences_memory_namespace", table_name="preferences")
    op.drop_index("ix_preferences_tenant_id", table_name="preferences")
    op.drop_table("preferences")

    op.drop_index(
        "ix_long_term_memory_entries_memory_namespace", table_name="long_term_memory_entries"
    )
    op.drop_index("ix_long_term_memory_entries_tenant_id", table_name="long_term_memory_entries")
    op.drop_table("long_term_memory_entries")

    op.drop_index("ix_conversation_turns_memory_namespace", table_name="conversation_turns")
    op.drop_index("ix_conversation_turns_tenant_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")
