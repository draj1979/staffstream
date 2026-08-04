import uuid

import httpx

from .config import settings


class AgentClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Agent Registry returned {status_code}: {detail}")


async def get_agent_for_employee(employee_id: uuid.UUID, *, bearer_token: str) -> dict:
    """Always fetched fresh from Agent Registry — no in-process caching, so
    an agent config change takes effect on the very next chat turn.

    Forwards the caller's own bearer token rather than minting a new one:
    the caller already has a valid session for this tenant/employee, and
    Agent Registry's read routes accept any authenticated employee of the
    same tenant, so there's no separate identity to establish here.
    """
    async with httpx.AsyncClient(base_url=settings.agent_registry_url, timeout=10.0) as client:
        resp = await client.get(
            f"/agents/by-employee/{employee_id}",
            headers={"Authorization": bearer_token},
        )
    if resp.status_code >= 400:
        raise AgentClientError(resp.status_code, resp.text)
    return resp.json()
