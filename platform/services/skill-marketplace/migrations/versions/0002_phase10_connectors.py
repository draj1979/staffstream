"""Phase 10: add connection_metadata column + seed the ten new connectors
into the skills catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_CATALOG = [
    {
        "skill_id": "salesforce",
        "name": "Salesforce",
        "description": "Query and create records in the employee's own Salesforce org.",
        "connector": "salesforce",
    },
    {
        "skill_id": "hubspot",
        "name": "HubSpot",
        "description": "Search and create CRM contacts in HubSpot.",
        "connector": "hubspot",
    },
    {
        "skill_id": "jira",
        "name": "Jira",
        "description": "Search and create issues in Jira the employee has access to.",
        "connector": "jira",
    },
    {
        "skill_id": "github",
        "name": "GitHub",
        "description": "List and create issues in GitHub repos the employee has access to.",
        "connector": "github",
    },
    {
        "skill_id": "microsoft_teams",
        "name": "Microsoft Teams",
        "description": (
            "Read and post messages in Microsoft Teams channels the employee belongs to."
        ),
        "connector": "microsoft_teams",
    },
    {
        "skill_id": "microsoft_365",
        "name": "Microsoft 365",
        "description": "Read and send the employee's own Outlook mail via Microsoft Graph.",
        "connector": "microsoft_365",
    },
    {
        "skill_id": "servicenow",
        "name": "ServiceNow",
        "description": "Search and create incidents in the tenant's ServiceNow instance.",
        "connector": "servicenow",
    },
    {
        "skill_id": "sap",
        "name": "SAP",
        "description": "Look up business partners and create sales orders in SAP S/4HANA Cloud.",
        "connector": "sap",
    },
    {
        "skill_id": "oracle",
        "name": "Oracle",
        "description": "Look up suppliers and create purchase orders in Oracle Fusion Cloud.",
        "connector": "oracle",
    },
    {
        "skill_id": "whatsapp",
        "name": "WhatsApp",
        "description": "Send WhatsApp Business messages on the employee's connected number.",
        "connector": "whatsapp",
    },
]


def upgrade() -> None:
    op.add_column(
        "employee_connections",
        sa.Column(
            "connection_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )

    skills = sa.table(
        "skills",
        sa.column("skill_id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("connector", sa.String),
    )
    op.bulk_insert(skills, _NEW_CATALOG)


def downgrade() -> None:
    skills = sa.table("skills", sa.column("skill_id", sa.String))
    op.execute(
        skills.delete().where(skills.c.skill_id.in_([row["skill_id"] for row in _NEW_CATALOG]))
    )
    op.drop_column("employee_connections", "connection_metadata")
