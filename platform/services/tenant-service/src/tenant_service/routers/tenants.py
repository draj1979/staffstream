import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, Role, require_auth, require_role
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish

from .. import crud
from ..db import get_db
from ..dependencies import get_publisher
from ..schemas import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])

# Only a platform-internal caller (system-scoped token) may list every
# tenant — no employee JWT should ever see other companies' tenant rows.
system_auth = require_auth(allowed_scopes=("system",))
# Reading a specific tenant requires a real employee of THAT tenant
# (enforced below, since Tenant isn't itself tenant-scoped and so gets no
# automatic filtering from the tenancy ORM layer) — or a system-scoped
# token for the one tenant it names, same bootstrap pattern as Employee
# Service's own by-id/by-email routes. Employee Service's agent-creation
# flow (Phase 10) is the current system-scoped caller, reading
# llm_config to pick a new agent's default provider/model.
user_auth = require_auth()
bootstrap_auth = require_auth(allowed_scopes=("user", "system"))
# Changing tenant settings is admin-only, on top of the same-tenant check.
admin_auth = require_role(Role.ADMIN.value)


def _require_self_tenant(principal: Principal, tenant_id: uuid.UUID) -> None:
    if principal.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access another tenant's data",
        )


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(data: TenantCreate, db: AsyncSession = Depends(get_db)):
    """Deliberately unauthenticated: this is the platform onboarding entry
    point — a new organization has no employee, and therefore no token,
    until after its tenant exists and its first employee signs up."""
    return await crud.create_tenant(db, data)


@router.get("", response_model=list[TenantOut])
async def list_tenants(
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(system_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_tenants(db, limit=limit, offset=offset)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(bootstrap_auth),
    db: AsyncSession = Depends(get_db),
):
    _require_self_tenant(principal, tenant_id)
    tenant = await crud.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    request: Request,
    principal: Principal = Depends(admin_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    _require_self_tenant(principal, tenant_id)
    tenant = await crud.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    updated = await crud.update_tenant(db, tenant, data)

    event = AuditEvent(
        tenant_id=tenant_id,
        actor_employee_id=principal.employee_id,
        action="tenant.updated",
        target_type="tenant",
        target_id=str(tenant_id),
        metadata=data.model_dump(exclude_unset=True),
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )
    return updated
