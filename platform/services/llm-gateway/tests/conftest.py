import pytest
from httpx import ASGITransport, AsyncClient
from llm_gateway.dependencies import get_gateway
from llm_gateway.gateway import LLMGateway
from llm_gateway.main import app
from llm_gateway.models import LLMResponse, Usage
from llm_gateway.provider import Provider


class StubProvider(Provider):
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


@pytest.fixture
def stub_gateway():
    gateway = LLMGateway()
    stub = StubProvider()
    gateway.register_provider("claude", stub)
    gateway.register_provider("stub-only", stub)
    return gateway, stub


@pytest.fixture
async def client(stub_gateway):
    gateway, _ = stub_gateway

    def override_get_gateway():
        return gateway

    app.dependency_overrides[get_gateway] = override_get_gateway
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
