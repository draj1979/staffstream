import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, Role, require_auth, require_role, role_satisfies
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish

from .. import crud
from ..db import get_db
from ..dependencies import get_publisher
from ..models import Agent
from ..schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])

# The auto-create call from Employee Service (a short-lived "system" token)
# happens right after an employee is created, before that employee has ever
# logged in — same bootstrap pattern as Employee Service's own create route.
user_auth = require_auth()
bootstrap_auth = require_auth(allowed_scopes=("user", "system"))
# Listing every agent in the tenant (prompts, personalities, everything)
# is manager+ only — a plain employee uses /agents/by-employee/{own id}
# for their own agent instead.
manager_auth = require_role(Role.MANAGER.value)


def _require_self_or_role(principal: Principal, agent: Agent, minimum: str) -> None:
    if agent.employee_id == principal.employee_id:
        return
    if role_satisfies(principal.role, minimum):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access another employee's agent",
    )


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    principal: Principal = Depends(bootstrap_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await crud.create_agent(db, data)
    except crud.DuplicateAgentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[AgentOut])
async def list_agents(
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(manager_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_agents(db, limit=limit, offset=offset)


@router.get("/by-employee/{employee_id}", response_model=AgentOut)
async def get_agent_by_employee(
    employee_id: uuid.UUID,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    agent = await crud.get_agent_by_employee(db, employee_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    _require_self_or_role(principal, agent, Role.MANAGER.value)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    agent = await crud.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    _require_self_or_role(principal, agent, Role.MANAGER.value)
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    request: Request,
    principal: Principal = Depends(user_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    agent = await crud.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    # Editing config (prompt, model, skills, ...) is tighter than viewing
    # it: the employee themselves, or an admin — a manager can look but
    # not touch someone else's agent.
    _require_self_or_role(principal, agent, Role.ADMIN.value)

    updated = await crud.update_agent(db, agent, data)

    event = AuditEvent(
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="agent.updated",
        target_type="agent",
        target_id=str(agent_id),
        metadata={"changed_fields": list(data.model_dump(exclude_unset=True))},
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )
    return updated
