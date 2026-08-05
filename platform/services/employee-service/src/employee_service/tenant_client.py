import uuid

import httpx

from auth import encode_system_token

from .config import settings


class TenantClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Tenant Service returned {status_code}: {detail}")


async def get_llm_defaults(tenant_id: uuid.UUID) -> tuple[str | None, str | None]:
    """Reads `(default_provider, default_model)` out of the tenant's own
    `llm_config` JSON blob — the convention CLAUDE.md's data model anchors
    document for "LLM config" on Tenant. Returns `(None, None)` on any
    failure (unset keys, unreachable Tenant Service, tenant not found)
    rather than raising: a missing per-tenant default should fall back to
    Agent Registry's own hardcoded default, not block employee creation.
    """
    system_token = encode_system_token(tenant_id)
    try:
        async with httpx.AsyncClient(base_url=settings.tenant_service_url, timeout=10.0) as client:
            resp = await client.get(
                f"/tenants/{tenant_id}", headers={"Authorization": f"Bearer {system_token}"}
            )
    except httpx.HTTPError:
        return None, None
    if resp.status_code >= 400:
        return None, None

    llm_config = resp.json().get("llm_config") or {}
    return llm_config.get("default_provider"), llm_config.get("default_model")
