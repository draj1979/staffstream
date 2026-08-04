import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, require_auth

from .. import crud
from ..db import get_db
from ..schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])

# The auto-create call from Employee Service (a short-lived "system" token)
# happens right after an employee is created, before that employee has ever
# logged in — same bootstrap pattern as Employee Service's own create route.
user_auth = require_auth()
bootstrap_auth = require_auth(allowed_scopes=("user", "system"))


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
    principal: Principal = Depends(user_auth),
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
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    agent = await crud.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return await crud.update_agent(db, agent, data)
