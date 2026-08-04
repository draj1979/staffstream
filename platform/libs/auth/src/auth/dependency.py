"""FastAPI dependency that verifies a bearer JWT and establishes the
tenant context for the request — the Phase 2 replacement for
tenancy.tenant_context's X-Tenant-Id header bridge.
"""

import uuid
from collections.abc import AsyncIterator, Callable

from fastapi import Header, HTTPException, status

from tenancy import reset_current_tenant_id, set_current_tenant_id

from .errors import InvalidTokenError
from .jwt import decode_token
from .principal import Principal


def require_auth(
    allowed_scopes: tuple[str, ...] = ("user",),
) -> Callable[..., AsyncIterator[Principal]]:
    """Build a dependency requiring a valid bearer token whose `scope` claim
    is one of `allowed_scopes`. Most routes want the default (`"user"`
    only); the one endpoint that must also accept auth-service's internal
    bootstrap call passes `allowed_scopes=("user", "system")`.
    """

    async def dependency(
        authorization: str | None = Header(default=None),
    ) -> AsyncIterator[Principal]:
        if authorization is None or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header",
            )
        token = authorization.split(" ", 1)[1]
        try:
            claims = decode_token(token)
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc

        scope = claims.get("scope")
        if scope not in allowed_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token scope {scope!r} is not permitted for this endpoint",
            )

        tenant_id = uuid.UUID(claims["tenant_id"])
        employee_id = None if scope == "system" else uuid.UUID(claims["sub"])

        token_ctx = set_current_tenant_id(tenant_id)
        try:
            yield Principal(tenant_id=tenant_id, scope=scope, employee_id=employee_id)
        finally:
            reset_current_tenant_id(token_ctx)

    return dependency
