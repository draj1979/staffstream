import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from tenancy import (
    Base,
    TenantContextError,
    TenantMismatchError,
    TenantScopedBase,
    clear_current_tenant_id,
    get_current_tenant_id,
    make_engine,
    make_session_factory,
    reset_current_tenant_id,
    set_current_tenant_id,
)


class Widget(TenantScopedBase):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]


@pytest.fixture
async def session_factory():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield make_session_factory(engine)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    yield
    clear_current_tenant_id()


async def test_query_without_tenant_context_raises(session_factory):
    async with session_factory() as session:
        with pytest.raises(TenantContextError):
            await session.execute(select(Widget))


async def test_insert_is_stamped_with_current_tenant(session_factory):
    tenant_id = uuid.uuid4()
    token = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            widget = Widget(id=uuid.uuid4(), name="left-handed smoke shifter")
            session.add(widget)
            await session.commit()
            assert widget.tenant_id == tenant_id
    finally:
        reset_current_tenant_id(token)


async def test_insert_rejects_mismatched_tenant_id(session_factory):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    token = set_current_tenant_id(tenant_a)
    try:
        async with session_factory() as session:
            widget = Widget(id=uuid.uuid4(), name="spanner", tenant_id=tenant_b)
            session.add(widget)
            with pytest.raises(TenantMismatchError):
                await session.commit()
    finally:
        reset_current_tenant_id(token)


async def test_select_only_returns_current_tenants_rows(session_factory):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()

    for tenant_id, name in [(tenant_a, "a-widget"), (tenant_b, "b-widget")]:
        token = set_current_tenant_id(tenant_id)
        try:
            async with session_factory() as session:
                session.add(Widget(id=uuid.uuid4(), name=name))
                await session.commit()
        finally:
            reset_current_tenant_id(token)

    token = set_current_tenant_id(tenant_a)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(Widget))).scalars().all()
            assert [w.name for w in rows] == ["a-widget"]
            assert all(w.tenant_id == tenant_a for w in rows)
    finally:
        reset_current_tenant_id(token)


def test_get_current_tenant_id_raises_without_context():
    with pytest.raises(TenantContextError):
        get_current_tenant_id()
