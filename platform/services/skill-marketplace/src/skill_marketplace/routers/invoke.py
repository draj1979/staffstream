from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, require_auth

from .. import crud
from ..connectors import CONNECTOR_REGISTRY, ConnectorError
from ..crypto import decrypt_token
from ..db import get_db
from ..dependencies import get_http_client
from ..schemas import InvokeRequest, InvokeResponse

router = APIRouter(prefix="/skills", tags=["invoke"])
user_auth = require_auth()


@router.post("/{skill_id}/invoke", response_model=InvokeResponse)
async def invoke_skill(
    skill_id: str,
    data: InvokeRequest,
    principal: Principal = Depends(user_auth),
    http: httpx.AsyncClient = Depends(get_http_client),
    db: AsyncSession = Depends(get_db),
):
    """The one place a tool call actually reaches Slack/Google. Three
    independent gates, all of which must hold, in order from cheapest to
    most expensive to check:

    1. The skill exists and the tenant has it enabled (tenant opt-in).
    2. This employee has their own connection for it (their OAuth grant).
    3. The provider itself accepts the call with that employee's token —
       the real, final authorization boundary; nothing this service does
       can make a call succeed that the employee's own grant doesn't
       already permit at Slack/Google's end.
    """
    connector = CONNECTOR_REGISTRY.get(skill_id)
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown skill")
    enablement = await crud.get_enablement(db, skill_id)
    if enablement is None or not enablement.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This skill is not enabled for your organization",
        )

    connection = await crud.get_connection(db, principal.employee_id, skill_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have not connected your account for this skill",
        )

    if (
        connector.supports_refresh
        and connection.refresh_token_encrypted
        and crud.token_needs_refresh(connection, now=datetime.now(UTC))
    ):
        try:
            refreshed = await connector.refresh(
                refresh_token=decrypt_token(connection.refresh_token_encrypted),
                http=http,
                tenant_config=enablement.config,
            )
        except ConnectorError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Token refresh failed: {exc}"
            ) from exc
        connection = await crud.update_connection_tokens(db, connection, refreshed)

    access_token = decrypt_token(connection.access_token_encrypted)
    try:
        output = await connector.invoke(
            tool_name=data.tool_name,
            tool_input=data.input,
            access_token=access_token,
            http=http,
            extra=connection.connection_metadata,
        )
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return InvokeResponse(output=output)
