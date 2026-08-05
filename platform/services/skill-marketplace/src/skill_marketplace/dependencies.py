import httpx
from fastapi import Request

from events import Publisher


def get_http_client(request: Request) -> httpx.AsyncClient:
    """A single shared client for every outbound call to Slack/Google —
    swapped for a `httpx.MockTransport`-backed client in tests via
    dependency override, so connector code never has to know it's not
    talking to the real internet."""
    return request.app.state.http_client


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher
