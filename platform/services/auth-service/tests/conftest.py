import asyncio
import uuid

import httpx
import pytest
from auth_service import db, employee_client
from auth_service.db import get_db
from auth_service.dependencies import get_http_client, get_publisher
from auth_service.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from events import Publisher
from tenancy import Base, make_engine, make_session_factory


@pytest.fixture
def fake_employee_service(monkeypatch):
    """Stubs the HTTP calls to Employee Service so auth-service tests
    don't need a real Employee Service running. Returns the dict of
    created employees keyed by email, for assertions — and backs
    get_employee/get_employee_by_email off the same store, so a role set
    at creation (or mutated directly in the dict by a test) is what
    login/refresh/SSO callback see."""
    created: dict[str, dict] = {}

    async def fake_create_employee(tenant_id, *, email, department, designation, phone, roles):
        employee = {
            "employee_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "email": email,
            "department": department,
            "designation": designation,
            "phone": phone,
            "roles": roles,
        }
        created[email] = employee
        return employee

    async def fake_get_employee(tenant_id, employee_id):
        for employee in created.values():
            if employee["employee_id"] == str(employee_id):
                return employee
        return None

    async def fake_get_employee_by_email(tenant_id, email):
        return created.get(email)

    monkeypatch.setattr(employee_client, "create_employee", fake_create_employee)
    monkeypatch.setattr(employee_client, "get_employee", fake_get_employee)
    monkeypatch.setattr(employee_client, "get_employee_by_email", fake_get_employee_by_email)
    monkeypatch.setattr(
        "auth_service.routers.auth.create_employee", fake_create_employee, raising=True
    )
    monkeypatch.setattr(
        "auth_service.routers.auth.get_employee", fake_get_employee, raising=True
    )
    monkeypatch.setattr(
        "auth_service.routers.sso.get_employee_by_email", fake_get_employee_by_email, raising=True
    )
    return created


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
async def client(monkeypatch, http_handler, fake_publisher):
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = make_session_factory(engine)
    monkeypatch.setattr(db, "engine", engine)  # so /readyz checks the test DB, not the real one

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
        await engine.dispose()
