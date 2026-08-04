import httpx
import pytest
from api_gateway.dependencies import get_http_client, get_rate_limiter, get_redis
from api_gateway.main import app
from api_gateway.rate_limit import RateLimiter
from httpx import ASGITransport, AsyncClient


class FakeHTTPClient:
    """Stands in for the real httpx.AsyncClient used to call upstream
    services. Tests register canned responses (or exceptions) per
    (method, url); every call is recorded for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.responses: dict[tuple[str, str], httpx.Response | Exception] = {}

    def set_response(self, method: str, url: str, response: httpx.Response) -> None:
        self.responses[(method, url)] = response

    def set_error(self, method: str, url: str, exc: Exception) -> None:
        self.responses[(method, url)] = exc

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        result = self.responses.get((method, url))
        if isinstance(result, Exception):
            raise result
        if result is not None:
            return result
        return httpx.Response(200, json={"ok": True})


class FakeRedis:
    """In-memory stand-in for the four Redis operations the gateway
    actually uses — no fixture library needed for something this small."""

    def __init__(self):
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        return 30

    async def ping(self) -> bool:
        return True


@pytest.fixture
def fake_http_client():
    return FakeHTTPClient()


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
async def client(fake_http_client, fake_redis):
    rate_limiter = RateLimiter(fake_redis, max_requests=1000, window_seconds=60)

    app.dependency_overrides[get_http_client] = lambda: fake_http_client
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.fake_http_client = fake_http_client  # type: ignore[attr-defined]
            ac.rate_limiter = rate_limiter  # type: ignore[attr-defined]
            ac.fake_redis = fake_redis  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
