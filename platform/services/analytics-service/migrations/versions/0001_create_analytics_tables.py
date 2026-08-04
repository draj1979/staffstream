"""create analytics tables: llm_usage_events, chat_interaction_events, skill_usage_events

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_events_tenant_id", "llm_usage_events", ["tenant_id"])
    op.create_index("ix_llm_usage_events_employee_id", "llm_usage_events", ["employee_id"])
    op.create_index("ix_llm_usage_events_agent_id", "llm_usage_events", ["agent_id"])
    op.create_index("ix_llm_usage_events_model", "llm_usage_events", ["model"])
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])

    op.create_table(
        "chat_interaction_events",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_stage", sa.String(length=50), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_chat_interaction_events_tenant_id", "chat_interaction_events", ["tenant_id"]
    )
    op.create_index(
        "ix_chat_interaction_events_employee_id", "chat_interaction_events", ["employee_id"]
    )
    op.create_index(
        "ix_chat_interaction_events_agent_id", "chat_interaction_events", ["agent_id"]
    )
    op.create_index(
        "ix_chat_interaction_events_created_at", "chat_interaction_events", ["created_at"]
    )

    op.create_table(
        "skill_usage_events",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_skill_usage_events_tenant_id", "skill_usage_events", ["tenant_id"])
    op.create_index("ix_skill_usage_events_employee_id", "skill_usage_events", ["employee_id"])
    op.create_index("ix_skill_usage_events_agent_id", "skill_usage_events", ["agent_id"])
    op.create_index("ix_skill_usage_events_skill_name", "skill_usage_events", ["skill_name"])
    op.create_index("ix_skill_usage_events_created_at", "skill_usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_skill_usage_events_created_at", table_name="skill_usage_events")
    op.drop_index("ix_skill_usage_events_skill_name", table_name="skill_usage_events")
    op.drop_index("ix_skill_usage_events_agent_id", table_name="skill_usage_events")
    op.drop_index("ix_skill_usage_events_employee_id", table_name="skill_usage_events")
    op.drop_index("ix_skill_usage_events_tenant_id", table_name="skill_usage_events")
    op.drop_table("skill_usage_events")

    op.drop_index("ix_chat_interaction_events_created_at", table_name="chat_interaction_events")
    op.drop_index("ix_chat_interaction_events_agent_id", table_name="chat_interaction_events")
    op.drop_index(
        "ix_chat_interaction_events_employee_id", table_name="chat_interaction_events"
    )
    op.drop_index("ix_chat_interaction_events_tenant_id", table_name="chat_interaction_events")
    op.drop_table("chat_interaction_events")

    op.drop_index("ix_llm_usage_events_created_at", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_model", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_agent_id", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_employee_id", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_tenant_id", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
