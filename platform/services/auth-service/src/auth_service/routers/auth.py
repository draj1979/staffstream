import secrets
import uuid
from datetime import UTC, datetime, timedelta

from auth.config import ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_DAYS
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    InvalidTokenError,
    Principal,
    Role,
    decode_token,
    encode_access_token,
    encode_state_token,
    hash_password_async,
    highest_role,
    require_role,
    verify_password_async,
)
from tenancy import reset_current_tenant_id, set_current_tenant_id, tenant_context

from .. import crud
from ..db import get_db
from ..employee_client import EmployeeServiceError, create_employee, get_employee
from ..schemas import (
    InviteAcceptRequest,
    InviteOut,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])

manager_auth = require_role(Role.MANAGER.value)

# A week is generous enough that "the admin sent it Friday, the new hire
# starts Monday" doesn't expire mid-flow, short enough that a leaked link
# doesn't stay usable indefinitely.
INVITE_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


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
    role = await _current_role_or_403(tenant_id, credential.employee_id)
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
    # Checked (and can now reject) before the new pair is issued: an
    # employee deactivated mid-session loses access on their next refresh,
    # not just their next login — bounded by the access token's own TTL
    # (ACCESS_TOKEN_TTL_SECONDS) for the token already in their hand.
    role = await _current_role_or_403(tenant_id, token.employee_id)
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


@router.post("/invite/accept", response_model=TokenPair)
async def accept_invite(
    data: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
):
    """No auth — the new hire isn't logged in yet; the invite token itself
    is the credential that authorizes this call, same trust model as the
    SSO callback's `state` token (see routers/sso.py)."""
    try:
        claims = decode_token(data.token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite link"
        ) from exc
    if claims.get("purpose") != "state" or claims.get("kind") != "employee_invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not an invite token")

    tenant_id = uuid.UUID(claims["tenant_id"])
    employee_id = uuid.UUID(claims["employee_id"])
    email = claims["email"]

    token_ctx = set_current_tenant_id(tenant_id)
    try:
        if await crud.get_credential_by_email(db, email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This invite has already been used",
            )
        await crud.create_credential(
            db,
            employee_id=employee_id,
            email=email,
            password_hash=await hash_password_async(data.password),
        )
        role = await _current_role_or_403(tenant_id, employee_id)
        return await _issue_token_pair(db, tenant_id, employee_id, role=role)
    finally:
        reset_current_tenant_id(token_ctx)


@router.post("/invite/{employee_id}", response_model=InviteOut)
async def invite_employee(
    employee_id: uuid.UUID,
    principal: Principal = Depends(manager_auth),
    db: AsyncSession = Depends(get_db),
):
    """Admin/manager-created employees (POST /employees on Employee
    Service) get a record but no way to log in — this closes that gap.
    Issues a signed, single-purpose token embedding employee_id/tenant_id/
    email; the console hands the resulting link to the new hire however
    it currently does invites (see InviteOut's docstring — no email
    service exists in this platform to send it automatically). Registered
    after the static /invite/accept route above — Starlette matches path
    routes in declaration order, and a dynamic /invite/{employee_id}
    declared first would swallow "accept" as an (invalid) employee_id."""
    try:
        employee = await get_employee(principal.tenant_id, employee_id)
    except EmployeeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if await crud.get_credential_by_email(db, employee["email"]) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This employee already has login credentials",
        )

    token = encode_state_token(
        {
            "kind": "employee_invite",
            "tenant_id": str(principal.tenant_id),
            "employee_id": str(employee_id),
            "email": employee["email"],
        },
        ttl_seconds=INVITE_TOKEN_TTL_SECONDS,
    )
    return InviteOut(invite_token=token, expires_in=INVITE_TOKEN_TTL_SECONDS)


async def _current_role_or_403(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> str:
    """Always re-fetched from Employee Service, never cached — a role
    change (Phase 9's RBAC) takes effect on this employee's very next
    login/refresh, not whenever some cached copy happens to expire. Also
    the one place `active` (see employee-service's deactivate/reactivate
    routes) is enforced: a deactivated employee's credentials still
    verify correctly, they just never get a token minted."""
    try:
        employee = await get_employee(tenant_id, employee_id)
    except EmployeeServiceError:
        return "employee"
    if employee is None:
        return "employee"
    if not employee.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )
    return highest_role(employee.get("roles", []))
