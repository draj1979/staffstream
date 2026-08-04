import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from skill_marketplace import db
from skill_marketplace.db import get_db
from skill_marketplace.dependencies import get_http_client
from skill_marketplace.main import app
from skill_marketplace.models import Skill
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import Base, make_engine, make_session_factory


def _catalog() -> list[Skill]:
    # Built fresh per call, not module-level shared instances — reusing
    # the same ORM object across different tests' sessions/engines leaves
    # it "bound" to whichever session touched it first, so session.add()
    # in a later test silently no-ops instead of inserting.
    return [
        Skill(
            skill_id="slack",
            name="Slack",
            description="Read and post to Slack channels the employee belongs to.",
            connector="slack",
        ),
        Skill(
            skill_id="google_calendar",
            name="Google Calendar",
            description="Read and create events on the employee's own Google Calendar.",
            connector="google_calendar",
        ),
    ]


class HandlerBox:
    """A mutable box so each test can set its own outbound-HTTP behavior
    after the `client` fixture (and its MockTransport-backed http client)
    already exist — httpx.MockTransport's handler is otherwise fixed at
    construction time."""

    def __init__(self):
        self.handler = self._unset

    def _unset(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"No HTTP handler set for test call to {request.url}")


@pytest.fixture
async def session_factory(monkeypatch):
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = make_session_factory(engine)
    monkeypatch.setattr(db, "engine", engine)

    async with factory() as session:
        for skill in _catalog():
            session.add(skill)
        await session.commit()

    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def http_handler():
    return HandlerBox()


@pytest.fixture
async def client(session_factory, http_handler):
    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    def dispatch(request: httpx.Request) -> httpx.Response:
        return http_handler.handler(request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(dispatch))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_http_client] = lambda: mock_client
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await mock_client.aclose()
