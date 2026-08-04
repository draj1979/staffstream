"""Request-scoped current-tenant storage.

Backed by a contextvar so it's safe under asyncio concurrency (each
request/task gets its own value) without threading it through every
function call.
"""

from contextvars import ContextVar, Token
from uuid import UUID

from .errors import TenantContextError

_current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)


def set_current_tenant_id(tenant_id: UUID) -> Token:
    """Set the current tenant. Returns a token — pass it to reset_current_tenant_id
    in a `finally` block so nested/concurrent contexts unwind correctly."""
    return _current_tenant_id.set(tenant_id)


def reset_current_tenant_id(token: Token) -> None:
    _current_tenant_id.reset(token)


def get_current_tenant_id() -> UUID:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextError(
            "No tenant_id set in context; refusing to run a tenant-scoped query. "
            "Did you forget the tenant_context dependency on this route?"
        )
    return tenant_id


def try_get_current_tenant_id() -> UUID | None:
    return _current_tenant_id.get()


def clear_current_tenant_id() -> None:
    """Force the context back to unset. Intended for test teardown only —
    request handlers should use reset_current_tenant_id(token) instead."""
    _current_tenant_id.set(None)
