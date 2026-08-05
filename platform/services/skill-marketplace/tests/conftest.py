import asyncio

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from skill_marketplace import db
from skill_marketplace.db import get_db
from skill_marketplace.dependencies import get_http_client, get_publisher
from skill_marketplace.main import app
from skill_marketplace.models import Skill
from sqlalchemy.ext.asyncio import AsyncSession

from events import Publisher
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
        Skill(
            skill_id="salesforce",
            name="Salesforce",
            description="Query and create records in the employee's own Salesforce org.",
            connector="salesforce",
        ),
        Skill(
            skill_id="hubspot",
            name="HubSpot",
            description="Search and create CRM contacts in HubSpot.",
            connector="hubspot",
        ),
        Skill(
            skill_id="jira",
            name="Jira",
            description="Search and create issues in Jira the employee has access to.",
            connector="jira",
        ),
        Skill(
            skill_id="github",
            name="GitHub",
            description="List and create issues in GitHub repos the employee has access to.",
            connector="github",
        ),
        Skill(
            skill_id="microsoft_teams",
            name="Microsoft Teams",
            description=(
                "Read and post messages in Microsoft Teams channels the employee belongs to."
            ),
            connector="microsoft_teams",
        ),
        Skill(
            skill_id="microsoft_365",
            name="Microsoft 365",
            description="Read and send the employee's own Outlook mail via Microsoft Graph.",
            connector="microsoft_365",
        ),
        Skill(
            skill_id="servicenow",
            name="ServiceNow",
            description="Search and create incidents in the tenant's ServiceNow instance.",
            connector="servicenow",
        ),
        Skill(
            skill_id="sap",
            name="SAP",
            description="Look up business partners and create sales orders in SAP S/4HANA Cloud.",
            connector="sap",
        ),
        Skill(
            skill_id="oracle",
            name="Oracle",
            description="Look up suppliers and create purchase orders in Oracle Fusion Cloud.",
            connector="oracle",
        ),
        Skill(
            skill_id="whatsapp",
            name="WhatsApp",
            description="Send WhatsApp Business messages on the employee's connected number.",
            connector="whatsapp",
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
async def client(session_factory, http_handler, fake_publisher):
    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    def dispatch(request: httpx.Request) -> httpx.Response:
        return http_handler.handler(request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(dispatch))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_http_client] = lambda: mock_client
    app.dependency_overrides[get_publisher] = lambda: fake_publisher
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await mock_client.aclose()
