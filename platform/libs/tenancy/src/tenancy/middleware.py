"""FastAPI dependency that establishes the current tenant for a request.

Phase 1 note: tenant identity comes from the X-Tenant-Id header, set by
whatever's in front of the service (API Gateway, or a curl request during
local dev). Phase 2 replaces this with the tenant_id embedded in the
authenticated JWT — the dependency's return type (UUID) stays the same, so
routers built on top of it don't change.
"""

from uuid import UUID

from fastapi import Header, HTTPException, status

from .context import reset_current_tenant_id, set_current_tenant_id


async def tenant_context(x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-Id")):
    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required",
        )
    token = set_current_tenant_id(x_tenant_id)
    try:
        yield x_tenant_id
    finally:
        reset_current_tenant_id(token)
