import pytest
from audit_service import db
from audit_service.db import get_db
from audit_service.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import Base, make_engine, make_session_factory


@pytest.fixture
async def session_factory(monkeypatch):
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = make_session_factory(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionFactory", factory)
    import audit_service.ingestion as ingestion_module

    monkeypatch.setattr(ingestion_module, "SessionFactory", factory)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def client(session_factory):
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
