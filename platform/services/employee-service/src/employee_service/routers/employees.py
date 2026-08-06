import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, Role, require_auth, require_role, role_satisfies
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish

from .. import crud
from ..agent_registry_client import AgentRegistryError, create_default_agent
from ..db import get_db
from ..dependencies import get_publisher
from ..models import Employee
from ..schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate
from ..tenant_client import get_llm_defaults

router = APIRouter(prefix="/employees", tags=["employees"])

# The signup bootstrap call from auth-service (a short-lived "system" token)
# is the one caller allowed to create an employee before any employee of
# that tenant has logged in. Every other route requires a real user token.
user_auth = require_auth()
bootstrap_auth = require_auth(allowed_scopes=("user", "system"))
# A "user"-scoped caller creating/updating an employee needs at least
# manager rank; the system-scoped bootstrap path skips this entirely (see
# _enforce_create_permissions/_enforce_update_permissions below) — it's a
# different trust tier, not a role to rank.
manager_auth = require_role(Role.MANAGER.value)


async def _actor_department(db: AsyncSession, principal: Principal) -> str | None:
    actor = await crud.get_employee(db, principal.employee_id)
    return actor.department if actor is not None else None


async def _enforce_create_permissions(
    db: AsyncSession, principal: Principal, data: EmployeeCreate
) -> None:
    """The system-scoped signup bootstrap call skips this entirely — it's
    a different trust tier, not a role to rank. A "user"-scoped caller
    needs at least manager rank, and a manager (not admin) may only
    create an employee within their own department (ABAC)."""
    if principal.scope == "system":
        return
    if not role_satisfies(principal.role, Role.MANAGER.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating employees requires at least manager role",
        )
    if principal.role == Role.MANAGER.value:
        actor_department = await _actor_department(db, principal)
        if data.department != actor_department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers may only create employees in their own department",
            )


async def _enforce_update_permissions(
    db: AsyncSession, principal: Principal, employee, data: EmployeeUpdate
) -> None:
    updates = data.model_dump(exclude_unset=True)

    # Changing roles is how privilege escalation would happen, so it's
    # admin-only regardless of who else can touch this employee record.
    if "roles" in updates and not role_satisfies(principal.role, Role.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change an employee's roles",
        )

    if principal.role == Role.MANAGER.value:
        actor_department = await _actor_department(db, principal)
        if employee.department != actor_department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers may only manage employees in their own department",
            )
        # Reassigning someone out of a manager's department would let them
        # manage people no longer under their own oversight check above —
        # only admins can move an employee between departments.
        if "department" in updates and updates["department"] != employee.department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change an employee's department",
            )


def _publish_audit(
    request: Request,
    publisher: Publisher,
    *,
    tenant_id: uuid.UUID,
    actor_employee_id: uuid.UUID | None,
    action: str,
    target_id: uuid.UUID,
    metadata: dict,
) -> None:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_employee_id=actor_employee_id,
        action=action,
        target_type="employee",
        target_id=str(target_id),
        metadata=metadata,
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    request: Request,
    principal: Principal = Depends(bootstrap_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    await _enforce_create_permissions(db, principal, data)

    try:
        employee = await crud.create_employee(db, data)
    except crud.ManagerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Best-effort: a tenant without llm_config set (or an unreachable
    # Tenant Service) just falls through to Agent Registry's own
    # hardcoded default rather than blocking employee creation.
    default_provider, default_model = await get_llm_defaults(principal.tenant_id)
    try:
        agent = await create_default_agent(
            principal.tenant_id,
            employee_id=employee.employee_id,
            provider=default_provider,
            model=default_model,
        )
    except AgentRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    employee = await crud.set_agent_id(db, employee, uuid.UUID(agent["agent_id"]))

    _publish_audit(
        request,
        publisher,
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="employee.created",
        target_id=employee.employee_id,
        metadata={"email": employee.email, "department": employee.department},
    )
    return employee


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_employees(db, limit=limit, offset=offset)


@router.get("/by-email/{email}", response_model=EmployeeOut)
async def get_employee_by_email(
    email: str,
    principal: Principal = Depends(bootstrap_auth),
    db: AsyncSession = Depends(get_db),
):
    """system-or-user scoped: Auth Service's SSO callback (a system token,
    since the employee isn't authenticated yet at that point) is the main
    caller, alongside any regular authenticated lookup."""
    employee = await crud.get_employee_by_email(db, email)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID,
    principal: Principal = Depends(bootstrap_auth),
    db: AsyncSession = Depends(get_db),
):
    """system-or-user scoped: Auth Service's login/refresh/SSO-callback
    role lookup (auth_service.employee_client.get_employee) is a system
    token, since it runs before that employee necessarily has a live
    session of their own — same reasoning as the by-email route above."""
    employee = await crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    request: Request,
    principal: Principal = Depends(manager_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    employee = await crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    await _enforce_update_permissions(db, principal, employee, data)

    old_roles = list(employee.roles)
    try:
        updated = await crud.update_employee(db, employee, data)
    except crud.ManagerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    changed_fields = data.model_dump(exclude_unset=True)
    _publish_audit(
        request,
        publisher,
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="employee.updated",
        target_id=employee_id,
        metadata={"changed_fields": list(changed_fields)},
    )
    if "roles" in changed_fields and changed_fields["roles"] != old_roles:
        _publish_audit(
            request,
            publisher,
            tenant_id=principal.tenant_id,
            actor_employee_id=principal.employee_id,
            action="employee.role_changed",
            target_id=employee_id,
            metadata={"old_roles": old_roles, "new_roles": changed_fields["roles"]},
        )
    return updated


async def _set_active_state(
    employee_id: uuid.UUID,
    active: bool,
    request: Request,
    principal: Principal,
    publisher: Publisher,
    db: AsyncSession,
) -> Employee:
    employee = await crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Same manager-vs-admin boundary as update_employee: a manager may
    # only deactivate/reactivate within their own department.
    if principal.role == Role.MANAGER.value:
        actor_department = await _actor_department(db, principal)
        if employee.department != actor_department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers may only manage employees in their own department",
            )

    if employee.active == active:
        return employee

    updated = await crud.set_active(db, employee, active)
    _publish_audit(
        request,
        publisher,
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="employee.deactivated" if not active else "employee.reactivated",
        target_id=employee_id,
        metadata={},
    )
    return updated


@router.post("/{employee_id}/deactivate", response_model=EmployeeOut)
async def deactivate_employee(
    employee_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(manager_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Revokes login access without touching the employee's record, agent,
    memory, or audit trail — auth-service refuses to issue tokens for an
    inactive employee (see auth-service's login/refresh routes). Not a
    delete: there is no DELETE route on this resource by design."""
    return await _set_active_state(employee_id, False, request, principal, publisher, db)


@router.post("/{employee_id}/reactivate", response_model=EmployeeOut)
async def reactivate_employee(
    employee_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(manager_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    return await _set_active_state(employee_id, True, request, principal, publisher, db)
