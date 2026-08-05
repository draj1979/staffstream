from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response, status

from events import RabbitMQPublisher
from tenancy import check_db_ready

from . import db
from .config import settings
from .routers.auth import router as auth_router
from .routers.sso import router as sso_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.publisher = RabbitMQPublisher(settings.rabbitmq_url)
    app.state.http_client = httpx.AsyncClient(timeout=15.0)
    yield
    await app.state.publisher.close()
    await app.state.http_client.aclose()


app = FastAPI(title="Auth Service", lifespan=lifespan)
# Not inside lifespan: tests drive the app via ASGITransport, which never
# runs FastAPI's lifespan events, but routes still need somewhere to hold
# strong references to their fire-and-forget audit-publish tasks.
app.state.background_tasks = set()
app.include_router(auth_router)
app.include_router(sso_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response):
    try:
        await check_db_ready(db.engine)
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready"}
    return {"status": "ready"}
