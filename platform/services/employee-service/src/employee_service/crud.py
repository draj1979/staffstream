import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Employee
from .schemas import EmployeeCreate, EmployeeUpdate


class ManagerNotFoundError(ValueError):
    """Raised when manager_id doesn't resolve to an employee in the current tenant."""


async def _validate_manager(db: AsyncSession, manager_id: uuid.UUID | None) -> None:
    if manager_id is None:
        return
    manager = await db.get(Employee, manager_id)
    if manager is None:
        raise ManagerNotFoundError(f"manager_id {manager_id} is not an employee of this tenant")


async def create_employee(db: AsyncSession, data: EmployeeCreate) -> Employee:
    await _validate_manager(db, data.manager_id)
    employee = Employee(**data.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


async def get_employee(db: AsyncSession, employee_id: uuid.UUID) -> Employee | None:
    return await db.get(Employee, employee_id)


async def get_employee_by_email(db: AsyncSession, email: str) -> Employee | None:
    result = await db.execute(select(Employee).where(Employee.email == email))
    return result.scalar_one_or_none()


async def list_employees(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[Employee]:
    result = await db.execute(
        select(Employee).limit(limit).offset(offset).order_by(Employee.created_at)
    )
    return list(result.scalars().all())


async def update_employee(db: AsyncSession, employee: Employee, data: EmployeeUpdate) -> Employee:
    updates = data.model_dump(exclude_unset=True)
    if "manager_id" in updates:
        await _validate_manager(db, updates["manager_id"])
    for field, value in updates.items():
        setattr(employee, field, value)
    await db.commit()
    await db.refresh(employee)
    return employee


async def set_agent_id(db: AsyncSession, employee: Employee, agent_id: uuid.UUID) -> Employee:
    employee.agent_id = agent_id
    await db.commit()
    await db.refresh(employee)
    return employee


async def set_active(db: AsyncSession, employee: Employee, active: bool) -> Employee:
    employee.active = active
    await db.commit()
    await db.refresh(employee)
    return employee
