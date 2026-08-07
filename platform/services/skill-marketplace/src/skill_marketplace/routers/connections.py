import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import InvalidTokenError, Principal, decode_token, encode_state_token, require_auth
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish
from tenancy import reset_current_tenant_id, set_current_tenant_id

from .. import crud
from ..config import settings
from ..connectors import CONNECTOR_REGISTRY, ConnectorError
from ..db import get_db
from ..dependencies import get_http_client, get_publisher
from ..schemas import ConnectionOut

router = APIRouter(prefix="/connections", tags=["connections"])
user_auth = require_auth()


def _redirect_uri(skill_id: str) -> str:
    return f"{settings.public_base_url}/connections/{skill_id}/callback"


@router.get("", response_model=list[ConnectionOut])
async def list_connections(
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    connections = await crud.list_connections(db, principal.employee_id)
    by_skill = {c.skill_id: c for c in connections}
    return [
        ConnectionOut(
            skill_id=skill_id,
            connected=skill_id in by_skill,
            external_account=by_skill[skill_id].external_account if skill_id in by_skill else None,
            granted_scope=by_skill[skill_id].granted_scope if skill_id in by_skill else None,
            connected_at=by_skill[skill_id].created_at if skill_id in by_skill else None,
        )
        for skill_id in CONNECTOR_REGISTRY
    ]


@router.get("/{skill_id}/authorize")
async def authorize(
    skill_id: str,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    connector = CONNECTOR_REGISTRY.get(skill_id)
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown skill")
    enablement = await crud.get_enablement(db, skill_id)
    if enablement is None or not enablement.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This skill is not enabled for your organization",
        )
    if not connector.is_configured():
        # Caught here specifically so the employee never gets redirected
        # to the real provider at all — without this, a 307 to e.g.
        # Google with a placeholder client_id lands the employee on
        # Google's own raw "Error 401: invalid_client" page, with no way
        # back to this app and no indication of what actually went wrong
        # or who can fix it.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{skill_id} isn't fully set up yet — an admin needs to "
                "register a real OAuth app for it and set the "
                "credentials before anyone can connect."
            ),
        )

    # Signed, short-lived — the callback trusts tenant_id/employee_id/
    # skill_id from this token, not from anything an attacker could put
    # on the query string of a request that lands on the callback URL.
    state = encode_state_token(
        {
            "tenant_id": str(principal.tenant_id),
            "employee_id": str(principal.employee_id),
            "skill_id": skill_id,
        }
    )
    url = connector.authorize_url(
        state=state, redirect_uri=_redirect_uri(skill_id), tenant_config=enablement.config
    )
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/{skill_id}/callback", response_class=HTMLResponse)
async def callback(
    skill_id: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    http: httpx.AsyncClient = Depends(get_http_client),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    # No require_auth here — the redirect back from Slack/Google carries no
    # bearer token, only the signed `state` we minted in /authorize. That
    # signed state *is* the authentication for this request.
    if error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth error: {error}")
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
    if claims.get("purpose") != "state" or claims.get("skill_id") != skill_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State/skill mismatch")

    tenant_id = uuid.UUID(claims["tenant_id"])
    employee_id = uuid.UUID(claims["employee_id"])

    connector = CONNECTOR_REGISTRY.get(skill_id)
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown skill")

    token_ctx = set_current_tenant_id(tenant_id)
    try:
        enablement = await crud.get_enablement(db, skill_id)
        tenant_config = enablement.config if enablement is not None else {}
        try:
            tokens = await connector.exchange_code(
                code=code,
                redirect_uri=_redirect_uri(skill_id),
                http=http,
                tenant_config=tenant_config,
            )
        except ConnectorError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        await crud.upsert_connection(db, employee_id, skill_id, tokens)

        event = AuditEvent(
            tenant_id=tenant_id,
            actor_employee_id=employee_id,
            action="skill.connected",
            target_type="skill",
            target_id=skill_id,
            metadata={"external_account": tokens.external_account},
        )
        schedule_publish(
            request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
        )
    finally:
        reset_current_tenant_id(token_ctx)

    return (
        "<html><body><h3>Connected.</h3>"
        f"<p>{skill_id} is now connected. You can close this tab.</p></body></html>"
    )


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    skill_id: str,
    request: Request,
    principal: Principal = Depends(user_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    connection = await crud.get_connection(db, principal.employee_id, skill_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected")
    await crud.delete_connection(db, connection)

    event = AuditEvent(
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="skill.disconnected",
        target_type="skill",
        target_id=skill_id,
        metadata={},
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )
