import uuid

import pytest
from auth_service import db, employee_client
from auth_service.db import get_db
from auth_service.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import Base, make_engine, make_session_factory


@pytest.fixture
def fake_employee_service(monkeypatch):
    """Stubs the HTTP call to Employee Service so auth-service tests don't
    need a real Employee Service running. Returns the dict of created
    employees keyed by email, for assertions."""
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

    monkeypatch.setattr(employee_client, "create_employee", fake_create_employee)
    monkeypatch.setattr(
        "auth_service.routers.auth.create_employee", fake_create_employee, raising=True
    )
    return created


@pytest.fixture
async def client(monkeypatch):
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = make_session_factory(engine)
    monkeypatch.setattr(db, "engine", engine)  # so /readyz checks the test DB, not the real one

    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
