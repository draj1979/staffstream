import asyncio
import uuid

import pytest
from employee_service import db
from employee_service.db import get_db
from employee_service.dependencies import get_publisher
from employee_service.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from events import Publisher
from tenancy import Base, make_engine, make_session_factory


@pytest.fixture(autouse=True)
def fake_agent_registry(monkeypatch):
    """Stubs the HTTP call to Agent Registry so employee-service tests
    don't need a real Agent Registry running. Returns the dict of
    auto-created agents keyed by employee_id, for assertions."""
    created: dict[str, dict] = {}

    async def fake_create_default_agent(tenant_id, *, employee_id, provider=None, model=None):
        agent = {
            "agent_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "employee_id": str(employee_id),
            "provider": provider or "claude",
            "model": model or "claude-sonnet-5",
        }
        created[str(employee_id)] = agent
        return agent

    monkeypatch.setattr(
        "employee_service.routers.employees.create_default_agent", fake_create_default_agent
    )
    return created


class FakePublisher(Publisher):
    """Records every publish call and lets tests await until the
    fire-and-forget task on the other side has actually run — the route
    schedules with asyncio.create_task and returns before it completes."""

    def __init__(self):
        self.published: list[tuple[str, bytes]] = []
        self._event = asyncio.Event()

    async def publish(self, routing_key: str, payload: bytes) -> None:
        self.published.append((routing_key, payload))
        self._event.set()

    async def wait_for_publish(self, timeout: float = 1.0) -> None:
        await asyncio.wait_for(self._event.wait(), timeout=timeout)


@pytest.fixture
def fake_publisher():
    return FakePublisher()


@pytest.fixture
async def client(monkeypatch, fake_publisher):
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = make_session_factory(engine)
    monkeypatch.setattr(db, "engine", engine)  # so /readyz checks the test DB, not the real one

    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_publisher] = lambda: fake_publisher
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
