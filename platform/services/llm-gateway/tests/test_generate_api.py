import uuid

from auth import encode_access_token


def user_headers() -> dict:
    token = encode_access_token(uuid.uuid4(), uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def test_missing_authorization_header_is_401(client):
    resp = await client.post(
        "/generate",
        json={"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


async def test_generate_returns_provider_response(client, stub_gateway):
    resp = await client.post(
        "/generate",
        json={"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]},
        headers=user_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "echo: hi"
    assert body["usage"]["input_tokens"] == 3


async def test_generate_defaults_to_claude_provider(client, stub_gateway):
    _, stub = stub_gateway
    resp = await client.post(
        "/generate",
        json={"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]},
        headers=user_headers(),
    )
    assert resp.status_code == 200
    assert stub.received is not None


async def test_generate_rejects_unknown_provider(client):
    resp = await client.post(
        "/generate",
        json={
            "model": "gpt-5",
            "provider": "openai",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=user_headers(),
    )
    assert resp.status_code == 400


async def test_generate_rejects_temperature_out_of_range(client):
    resp = await client.post(
        "/generate",
        json={
            "model": "claude-sonnet-5",
            "temperature": 5.0,
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=user_headers(),
    )
    assert resp.status_code == 422
