"""Keeps an employee's agent's own `skills` allowlist in sync with what
they've actually connected here — see routers/connections.py's callback
and disconnect handlers, the only two callers. Uses a short-lived
system-scoped token, same pattern as
employee_service.agent_registry_client.create_default_agent: this
service has no bearer token of its own to act with (the OAuth callback
in particular runs with no Authorization header at all, only the signed
state — see connections.py's own comment on that), so it mints one
scoped to the tenant the skill was just connected under.

Deliberately best-effort: both callers treat a failure here as
"log it, don't fail the request" — by the time either of these runs, the
OAuth token exchange (connect) or connection deletion (disconnect) has
already succeeded, and failing the whole request over a *secondary*
sync step would be a worse outcome than the agent's allowlist staying
one call behind until the next attempt.
"""

import logging
import uuid

import httpx

from auth import encode_system_token

from .config import settings

logger = logging.getLogger(__name__)


class AgentRegistryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Agent Registry returned {status_code}: {detail}")


async def _call(method: str, tenant_id: uuid.UUID, employee_id: uuid.UUID, skill_id: str) -> None:
    system_token = encode_system_token(tenant_id)
    async with httpx.AsyncClient(base_url=settings.agent_registry_url, timeout=10.0) as client:
        resp = await client.request(
            method,
            f"/agents/by-employee/{employee_id}/skills/{skill_id}",
            headers={"Authorization": f"Bearer {system_token}"},
        )
    if resp.status_code >= 400:
        raise AgentRegistryError(resp.status_code, resp.text)


async def grant_skill(tenant_id: uuid.UUID, employee_id: uuid.UUID, skill_id: str) -> None:
    try:
        await _call("POST", tenant_id, employee_id, skill_id)
    except (AgentRegistryError, httpx.HTTPError) as exc:
        logger.error(
            "failed to grant %s to employee %s's agent after a successful connect: %s",
            skill_id,
            employee_id,
            exc,
        )


async def revoke_skill(tenant_id: uuid.UUID, employee_id: uuid.UUID, skill_id: str) -> None:
    try:
        await _call("DELETE", tenant_id, employee_id, skill_id)
    except (AgentRegistryError, httpx.HTTPError) as exc:
        logger.error(
            "failed to revoke %s from employee %s's agent after disconnect: %s",
            skill_id,
            employee_id,
            exc,
        )
