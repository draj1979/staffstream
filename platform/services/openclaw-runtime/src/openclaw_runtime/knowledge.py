"""Phase 5: real Knowledge Platform wiring. Given the employee's message,
retrieves relevant chunks from whichever scopes they can see — personal,
their own department, and company-wide — and formats them for the system
prompt. Always fetched fresh over HTTP; nothing is cached in this process
between requests.
"""

import uuid

from . import employee_client, knowledge_client


async def load_knowledge_context(
    tenant_id: uuid.UUID, employee_id: uuid.UUID, agent: dict, *, bearer_token: str, query: str
) -> str | None:
    employee = await employee_client.get_employee(employee_id, bearer_token=bearer_token)
    department = employee.get("department")

    results = await knowledge_client.search_knowledge(
        bearer_token=bearer_token,
        query=query,
        department=department,
        employee_id=employee_id,
    )
    if not results:
        return None

    return "\n\n".join(f"[{r['filename']}] {r['content']}" for r in results)
