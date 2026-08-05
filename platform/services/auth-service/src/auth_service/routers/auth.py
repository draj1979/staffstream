import secrets
import uuid
from datetime import UTC, datetime, timedelta

from auth.config import ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_DAYS
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    encode_access_token,
    hash_password_async,
    highest_role,
    verify_password_async,
)
from tenancy import tenant_context

from .. import crud
from ..db import get_db
from ..employee_client import EmployeeServiceError, create_employee, get_employee
from ..schemas import LoginRequest, LogoutRequest, RefreshRequest, SignupRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_token_pair(
    db: AsyncSession, tenant_id: uuid.UUID, employee_id: uuid.UUID, *, role: str
) -> TokenPair:
    access_token = encode_access_token(tenant_id, employee_id, role=role)
    raw_refresh_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await crud.create_refresh_token(
        db, employee_id=employee_id, raw_token=raw_refresh_token, expires_at=expires_at
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=ACCESS_TOKEN_TTL_SECONDS,
        tenant_id=tenant_id,
        employee_id=employee_id,
    )


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def signup(
    data: SignupRequest,
    tenant_id: uuid.UUID = Depends(tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if await crud.get_credential_by_email(db, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists for this tenant",
        )

    try:
        employee = await create_employee(
            tenant_id,
            email=data.email,
            department=data.department,
            designation=data.designation,
            phone=data.phone,
            roles=data.roles,
        )
    except EmployeeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    employee_id = uuid.UUID(employee["employee_id"])
    await crud.create_credential(
        db,
        employee_id=employee_id,
        email=data.email,
        password_hash=await hash_password_async(data.password),
    )
    return await _issue_token_pair(
        db, tenant_id, employee_id, role=highest_role(employee.get("roles", []))
    )


@router.post("/login", response_model=TokenPair)
async def login(
    data: LoginRequest,
    tenant_id: uuid.UUID = Depends(tenant_context),
    db: AsyncSession = Depends(get_db),
):
    credential = await crud.get_credential_by_email(db, data.email)
    if credential is None or not await verify_password_async(
        data.password, credential.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    role = await _current_role(tenant_id, credential.employee_id)
    return await _issue_token_pair(db, tenant_id, credential.employee_id, role=role)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    data: RefreshRequest,
    tenant_id: uuid.UUID = Depends(tenant_context),
    db: AsyncSession = Depends(get_db),
):
    token = await crud.get_active_refresh_token(db, data.refresh_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid, expired, or revoked",
        )
    # Rotate: the presented token is single-use, so a stolen-and-replayed
    # refresh token stops working the moment the legitimate client uses it.
    await crud.revoke_refresh_token(db, token)
    role = await _current_role(tenant_id, token.employee_id)
    return await _issue_token_pair(db, tenant_id, token.employee_id, role=role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: LogoutRequest,
    tenant_id: uuid.UUID = Depends(tenant_context),
    db: AsyncSession = Depends(get_db),
):
    token = await crud.get_active_refresh_token(db, data.refresh_token)
    if token is not None:
        await crud.revoke_refresh_token(db, token)


async def _current_role(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> str:
    """Always re-fetched from Employee Service, never cached — a role
    change (Phase 9's RBAC) takes effect on this employee's very next
    login/refresh, not whenever some cached copy happens to expire."""
    try:
        employee = await get_employee(tenant_id, employee_id)
    except EmployeeServiceError:
        return "employee"
    if employee is None:
        return "employee"
    return highest_role(employee.get("roles", []))
