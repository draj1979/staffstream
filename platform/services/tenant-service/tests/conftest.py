import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tenant_service import db
from tenant_service.db import get_db
from tenant_service.dependencies import get_publisher
from tenant_service.main import app

from events import Publisher
from tenancy import Base, make_engine, make_session_factory


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
