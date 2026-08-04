import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import tenant_context

from .. import crud
from ..db import get_db
from ..schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate

router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    dependencies=[Depends(tenant_context)],
)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await crud.create_employee(db, data)
    except crud.ManagerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[EmployeeOut])
async def list_employees(limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    return await crud.list_employees(db, limit=limit, offset=offset)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    employee = await crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID, data: EmployeeUpdate, db: AsyncSession = Depends(get_db)
):
    employee = await crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    try:
        return await crud.update_employee(db, employee, data)
    except crud.ManagerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
