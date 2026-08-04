import httpx
from starlette.requests import Request

from .rate_limit import RateLimiter


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_redis(request: Request):
    return request.app.state.redis


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter
