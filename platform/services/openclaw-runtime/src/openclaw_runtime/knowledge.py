"""Phase 5 stub. The real Knowledge Platform (company/department/personal
documents via pgvector) lands here — until then, OpenClaw never augments
the system prompt with retrieved knowledge.
"""

import uuid


async def load_knowledge_context(
    tenant_id: uuid.UUID, employee_id: uuid.UUID, agent: dict
) -> str | None:
    return None
