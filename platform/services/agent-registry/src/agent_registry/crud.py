import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import get_current_tenant_id

from .models import Agent
from .schemas import AgentCreate, AgentUpdate


class DuplicateAgentError(ValueError):
    """Raised when an employee already has an agent profile."""


async def get_agent_by_employee(db: AsyncSession, employee_id: uuid.UUID) -> Agent | None:
    result = await db.execute(select(Agent).where(Agent.employee_id == employee_id))
    return result.scalar_one_or_none()


async def create_agent(db: AsyncSession, data: AgentCreate) -> Agent:
    if await get_agent_by_employee(db, data.employee_id) is not None:
        raise DuplicateAgentError(f"Employee {data.employee_id} already has an agent profile")

    memory_namespace = data.memory_namespace or f"{get_current_tenant_id()}:{data.employee_id}"
    agent = Agent(**{**data.model_dump(), "memory_namespace": memory_namespace})
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    return await db.get(Agent, agent_id)


async def list_agents(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[Agent]:
    result = await db.execute(select(Agent).limit(limit).offset(offset).order_by(Agent.created_at))
    return list(result.scalars().all())


async def update_agent(db: AsyncSession, agent: Agent, data: AgentUpdate) -> Agent:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent
