import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud
from ..db import get_db
from ..schemas import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(data: TenantCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_tenant(db, data)


@router.get("", response_model=list[TenantOut])
async def list_tenants(limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    return await crud.list_tenants(db, limit=limit, offset=offset)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tenant = await crud.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: uuid.UUID, data: TenantUpdate, db: AsyncSession = Depends(get_db)
):
    tenant = await crud.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return await crud.update_tenant(db, tenant, data)
