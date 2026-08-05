"""FastAPI dependency that verifies a bearer JWT and establishes the
tenant context for the request — the Phase 2 replacement for
tenancy.tenant_context's X-Tenant-Id header bridge.
"""

import uuid
from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Header, HTTPException, status

from tenancy import reset_current_tenant_id, set_current_tenant_id

from .errors import InvalidTokenError
from .jwt import decode_token
from .principal import Principal
from .roles import role_satisfies


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
        # Defaults to "employee" for a "user"-scoped token that predates
        # the role claim (or whose role claim is missing/blank) — never
        # None, so a stale token can't accidentally satisfy a role check
        # against `role_satisfies(None, minimum)` (which treats None as
        # rank -1, below even "employee").
        role = (claims.get("role") or "employee") if scope == "user" else None

        token_ctx = set_current_tenant_id(tenant_id)
        try:
            yield Principal(tenant_id=tenant_id, scope=scope, employee_id=employee_id, role=role)
        finally:
            reset_current_tenant_id(token_ctx)

    return dependency


def require_role(minimum: str) -> Callable[..., AsyncIterator[Principal]]:
    """Build a dependency requiring a "user"-scoped token whose role is at
    least `minimum` in the admin > manager > employee hierarchy. System-
    scoped tokens never satisfy this — they're for service-to-service
    bootstrap calls, a different trust tier entirely, not a role to rank.
    """
    user_auth = require_auth(allowed_scopes=("user",))

    async def dependency(principal: Principal = Depends(user_auth)) -> Principal:
        if not role_satisfies(principal.role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {minimum!r} role, this token has {principal.role!r}",
            )
        return principal

    return dependency
