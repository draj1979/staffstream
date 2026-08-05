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
    """Every service's db.py calls this with just a URL, so the pool
    tuning that matters under multi-tenant load lives here once, not
    copy-pasted into 9 files.

    SQLAlchemy's own defaults (pool_size=5, max_overflow=10 -> 15
    connections per engine) were sized for a single app instance, not a
    k8s Deployment that HPA can scale out under load. A load test against
    the local stack (scripts/load_test.py) showed signup latency
    (a 3-hop chain through auth-service -> employee-service ->
    agent-registry, each with its own pool) growing from ~0.6s p50 to
    ~1.5s p50 and 2.3s p95 once concurrency crossed ~30 in-flight
    requests per pod — connections queuing behind the 15-connection cap,
    not CPU or the database itself.

    Bumped to pool_size=10/max_overflow=15 (25 per pod) as a better
    per-pod budget for that same scenario, still deliberately modest
    because it's multiplied by both HPA replica count *and* how many of
    the 8 services share the one Postgres instance (see
    infra/k8s/postgres.yaml's max_connections, sized with this budget in
    mind). pool_recycle avoids handing out a connection Postgres or a
    cloud LB has already dropped from under a long-lived pool; that
    matters more once pods live for days under HPA rather than being
    restarted often in dev. Callers can still override any of these via
    kwargs for a service with different needs (e.g. a lighter pool for a
    low-traffic service, or a bigger one for a proxy-heavy one).

    sqlite (used by every service's test suite, an in-memory StaticPool)
    doesn't accept pool_size/max_overflow/pool_timeout at all, so these
    are only applied for real (Postgres) URLs — tests get sqlite's own
    defaults untouched.
    """
    if not database_url.startswith("sqlite"):
        kwargs.setdefault("pool_size", 10)
        kwargs.setdefault("max_overflow", 15)
        kwargs.setdefault("pool_timeout", 30)
        kwargs.setdefault("pool_recycle", 1800)
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
