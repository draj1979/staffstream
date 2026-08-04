async def test_healthz_is_always_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ok_when_redis_reachable(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_readyz_503_when_redis_unreachable(client):
    async def broken_ping():
        raise ConnectionError("redis is down")

    client.fake_redis.ping = broken_ping

    resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not ready"}
