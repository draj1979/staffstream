import uuid

import httpx

from auth import encode_system_token

from .config import settings


class AgentRegistryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Agent Registry returned {status_code}: {detail}")


async def create_default_agent(
    tenant_id: uuid.UUID,
    *,
    employee_id: uuid.UUID,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """Provisions the default agent profile for a newly created employee,
    the same way auth-service provisions the employee itself: a real call
    to the owning service's own API, using a short-lived system-scoped
    token rather than touching its database directly. `provider`/`model`
    come from the tenant's own `llm_config` default when set (Phase 10 —
    see tenant_client.get_llm_defaults) so a tenant's chosen provider
    applies to every new employee's agent; omitted entirely when unset,
    letting Agent Registry's own hardcoded default apply instead.
    """
    payload: dict = {"employee_id": str(employee_id)}
    if provider is not None:
        payload["provider"] = provider
    if model is not None:
        payload["model"] = model

    system_token = encode_system_token(tenant_id)
    async with httpx.AsyncClient(base_url=settings.agent_registry_url, timeout=10.0) as client:
        resp = await client.post(
            "/agents",
            json=payload,
            headers={"Authorization": f"Bearer {system_token}"},
        )
    if resp.status_code >= 400:
        raise AgentRegistryError(resp.status_code, resp.text)
    return resp.json()
