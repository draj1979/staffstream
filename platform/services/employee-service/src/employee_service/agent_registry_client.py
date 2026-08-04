import uuid

import httpx

from auth import encode_system_token

from .config import settings


class AgentRegistryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Agent Registry returned {status_code}: {detail}")


async def create_default_agent(tenant_id: uuid.UUID, *, employee_id: uuid.UUID) -> dict:
    """Provisions the default agent profile for a newly created employee,
    the same way auth-service provisions the employee itself: a real call
    to the owning service's own API, using a short-lived system-scoped
    token rather than touching its database directly."""
    system_token = encode_system_token(tenant_id)
    async with httpx.AsyncClient(base_url=settings.agent_registry_url, timeout=10.0) as client:
        resp = await client.post(
            "/agents",
            json={"employee_id": str(employee_id)},
            headers={"Authorization": f"Bearer {system_token}"},
        )
    if resp.status_code >= 400:
        raise AgentRegistryError(resp.status_code, resp.text)
    return resp.json()
