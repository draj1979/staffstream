from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, Response, status

from .config import settings
from .dependencies import get_redis
from .proxy import router as proxy_router
from .rate_limit import RateLimiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=settings.upstream_timeout_seconds)
    app.state.redis = redis.from_url(settings.redis_url)
    app.state.rate_limiter = RateLimiter(
        app.state.redis,
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    yield
    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(title="API Gateway", lifespan=lifespan)


# Registered before the catch-all proxy route below: Starlette matches
# routes in registration order, and "/{path:path}" would otherwise swallow
# these two literal paths as well.
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response, redis_client=Depends(get_redis)):
    try:
        await redis_client.ping()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready"}
    return {"status": "ready"}


app.include_router(proxy_router)
