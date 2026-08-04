import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from llm_gateway.dependencies import get_gateway, get_publisher
from llm_gateway.gateway import LLMGateway
from llm_gateway.main import app
from llm_gateway.models import LLMResponse, Usage
from llm_gateway.provider import Provider as LLMProvider

from events import Publisher


class StubProvider(LLMProvider):
    def __init__(self):
        self.received = None

    async def complete(self, request):
        self.received = request
        return LLMResponse(
            content=f"echo: {request.messages[-1].content}",
            model=request.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=3, output_tokens=5),
        )


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
def stub_gateway():
    gateway = LLMGateway()
    stub = StubProvider()
    gateway.register_provider("claude", stub)
    gateway.register_provider("stub-only", stub)
    return gateway, stub


@pytest.fixture
def fake_publisher():
    return FakePublisher()


@pytest.fixture
async def client(stub_gateway, fake_publisher):
    gateway, _ = stub_gateway

    app.dependency_overrides[get_gateway] = lambda: gateway
    app.dependency_overrides[get_publisher] = lambda: fake_publisher
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
