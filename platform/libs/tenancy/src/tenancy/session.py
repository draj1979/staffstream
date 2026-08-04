"""The enforcement layer: wire this up once per service and every ORM
query against a TenantScopedBase subclass is automatically filtered to
the current tenant, with no per-query opt-in required.
"""

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, with_loader_criteria

from .base import TenantScopedBase
from .context import get_current_tenant_id
from .errors import TenantMismatchError


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state) -> None:
    """Injects `WHERE tenant_id = :current_tenant` into every SELECT/UPDATE/DELETE
    that touches a TenantScopedBase subclass. Registered once on the Session
    class, so it applies to every session in the process — including
    AsyncSession, which delegates ORM events to its underlying sync Session.

    Queries against non-tenant-scoped tables (e.g. Tenant itself) are left
    untouched: we check `all_mappers` up front, before ever asking for the
    current tenant, so those can run with no tenant context set at all.
    """
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return
    touches_tenant_scoped = any(
        issubclass(mapper.class_, TenantScopedBase) for mapper in execute_state.all_mappers
    )
    if not touches_tenant_scoped:
        return

    tenant_id = get_current_tenant_id()
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScopedBase,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(TenantScopedBase, "before_insert", propagate=True)
def _stamp_or_validate_tenant_id(mapper, connection, target: TenantScopedBase) -> None:
    """On insert: fill in tenant_id from context if the caller left it unset,
    or reject the insert outright if it was set to a different tenant than
    the current context (guards against a caller trying to write into
    another tenant's data)."""
    current = get_current_tenant_id()
    if target.tenant_id is None:
        target.tenant_id = current
    elif target.tenant_id != current:
        raise TenantMismatchError(
            f"Refusing to insert {type(target).__name__} with tenant_id={target.tenant_id} "
            f"while current tenant context is {current}"
        )


def make_engine(database_url: str, **kwargs) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True, **kwargs)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def check_db_ready(engine: AsyncEngine) -> None:
    """For a /readyz probe: raises if the DB isn't reachable right now.
    Deliberately not used for /healthz — a DB blip shouldn't make k8s
    restart a pod that's otherwise fine, only stop routing traffic to it."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
