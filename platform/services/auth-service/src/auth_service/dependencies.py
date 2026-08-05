import httpx
from fastapi import Request

from events import Publisher


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher


def get_http_client(request: Request) -> httpx.AsyncClient:
    """A single shared client for every outbound OIDC call (discovery,
    token exchange, JWKS) — swapped for a `httpx.MockTransport`-backed
    client in tests via dependency override."""
    return request.app.state.http_client
