import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    InvalidTokenError,
    Principal,
    Role,
    decode_token,
    encode_state_token,
    highest_role,
    require_role,
)
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish
from tenancy import reset_current_tenant_id, set_current_tenant_id

from .. import crud, oidc
from ..config import settings
from ..crypto import decrypt_secret
from ..db import get_db
from ..dependencies import get_http_client, get_publisher
from ..employee_client import EmployeeServiceError, get_employee_by_email
from ..schemas import SsoConfigIn, SsoConfigOut, TokenPair
from .auth import _issue_token_pair

router = APIRouter(prefix="/auth/sso", tags=["sso"])

# Configuring which IdP a tenant uses is admin-only, same tier as tenant
# settings changes elsewhere in the platform.
admin_auth = require_role(Role.ADMIN.value)

_SUPPORTED_PROVIDERS = {"google_workspace", "auth0"}


def _redirect_uri(provider: str) -> str:
    return f"{settings.public_base_url}/auth/sso/callback/{provider}"


def _require_known_provider(provider: str) -> None:
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown SSO provider")


@router.get("/config", response_model=list[SsoConfigOut])
async def list_sso_config(
    principal: Principal = Depends(admin_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_sso_connections(db)


@router.put("/config/{provider}", response_model=SsoConfigOut)
async def set_sso_config(
    provider: str,
    data: SsoConfigIn,
    request: Request,
    principal: Principal = Depends(admin_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    _require_known_provider(provider)
    if provider == "auth0" and not data.issuer_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth0 SSO requires issuer_domain (your tenant's Auth0 domain)",
        )

    connection = await crud.upsert_sso_connection(
        db,
        provider,
        client_id=data.client_id,
        client_secret=data.client_secret,
        issuer_domain=data.issuer_domain,
        hosted_domain=data.hosted_domain,
        enabled=data.enabled,
    )

    event = AuditEvent(
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="sso.config_changed",
        target_type="sso_connection",
        target_id=provider,
        metadata={"enabled": data.enabled, "issuer_domain": data.issuer_domain},
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )
    return connection


@router.get("/login/{tenant_id}/{provider}")
async def sso_login(
    tenant_id: uuid.UUID,
    provider: str,
    http: httpx.AsyncClient = Depends(get_http_client),
    db: AsyncSession = Depends(get_db),
):
    """No auth — the employee isn't logged in yet. tenant_id comes
    straight from the URL (a real frontend would route
    /login/{tenant-slug-or-id}/{provider}), not from a token."""
    _require_known_provider(provider)

    token_ctx = set_current_tenant_id(tenant_id)
    try:
        connection = await crud.get_sso_connection(db, provider)
    finally:
        reset_current_tenant_id(token_ctx)

    if connection is None or not connection.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not configured or not enabled for this tenant/provider",
        )

    try:
        discovery = await oidc.fetch_discovery(
            oidc.discovery_url(provider, issuer_domain=connection.issuer_domain), http=http
        )
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # Signed, short-lived — the callback trusts tenant_id/provider from
    # this token, not from anything an attacker could put on the query
    # string of a request that lands on the callback URL.
    state = encode_state_token({"tenant_id": str(tenant_id), "provider": provider})
    url = oidc.build_authorize_url(
        discovery,
        client_id=connection.client_id,
        redirect_uri=_redirect_uri(provider),
        state=state,
        hosted_domain=connection.hosted_domain,
    )
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback/{provider}", response_model=TokenPair)
async def sso_callback(
    provider: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    http: httpx.AsyncClient = Depends(get_http_client),
    db: AsyncSession = Depends(get_db),
):
    """Returns the token pair directly as JSON — there's no frontend in
    this repo yet to redirect to with a short-lived code or a cookie; a
    real deployment would hand off to one instead of returning tokens in
    a URL-reachable JSON body."""
    _require_known_provider(provider)
    if error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSO error: {error}")
    if code is None or state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state"
        )

    try:
        claims = decode_token(state)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state"
        ) from exc
    if claims.get("purpose") != "state" or claims.get("provider") != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="State/provider mismatch"
        )
    tenant_id = uuid.UUID(claims["tenant_id"])

    token_ctx = set_current_tenant_id(tenant_id)
    try:
        connection = await crud.get_sso_connection(db, provider)
        if connection is None or not connection.enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="SSO is not enabled for this tenant"
            )

        try:
            discovery = await oidc.fetch_discovery(
                oidc.discovery_url(provider, issuer_domain=connection.issuer_domain), http=http
            )
            token_response = await oidc.exchange_code(
                discovery,
                client_id=connection.client_id,
                client_secret=decrypt_secret(connection.client_secret_encrypted),
                code=code,
                redirect_uri=_redirect_uri(provider),
                http=http,
            )
            jwks = await oidc.fetch_jwks(discovery["jwks_uri"], http=http)
            id_claims = oidc.verify_id_token(
                token_response["id_token"],
                jwks=jwks,
                issuer=discovery["issuer"],
                audience=connection.client_id,
            )
        except oidc.OIDCError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        if provider == "google_workspace" and connection.hosted_domain:
            if id_claims.get("hd") != connection.hosted_domain:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Google account is not a member of this organization's Workspace domain",
                )

        email = id_claims.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="id_token did not include an email claim",
            )

        try:
            employee = await get_employee_by_email(tenant_id, email)
        except EmployeeServiceError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
        if employee is None:
            # Deliberately no auto-provisioning this phase — SSO maps to
            # an *existing* employee_id/tenant_id, it doesn't mint a new
            # identity. An admin creates the employee record first (same
            # as any other employee), then that person can log in via SSO.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No employee found for {email!r} in this tenant",
            )

        if not employee.get("active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated",
            )

        employee_id = uuid.UUID(employee["employee_id"])
        role = highest_role(employee.get("roles", []))
        return await _issue_token_pair(db, tenant_id, employee_id, role=role)
    finally:
        reset_current_tenant_id(token_ctx)
