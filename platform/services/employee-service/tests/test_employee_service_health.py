async def test_healthz_is_always_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ok_when_db_reachable(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_readyz_503_when_db_unreachable(client, monkeypatch):
    from employee_service import db

    broken_engine = db.make_engine("postgresql+asyncpg://nobody:nowhere@localhost:1/nope")
    monkeypatch.setattr(db, "engine", broken_engine)

    resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not ready"}
