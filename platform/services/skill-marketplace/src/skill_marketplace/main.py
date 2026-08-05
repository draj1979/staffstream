from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response, status

from events import RabbitMQPublisher
from tenancy import check_db_ready

from . import db
from .config import settings
from .routers.connections import router as connections_router
from .routers.invoke import router as invoke_router
from .routers.skills import router as skills_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=15.0)
    app.state.publisher = RabbitMQPublisher(settings.rabbitmq_url)
    yield
    await app.state.http_client.aclose()
    await app.state.publisher.close()


app = FastAPI(title="Skill Marketplace", lifespan=lifespan)
# Not inside lifespan: tests drive the app via ASGITransport, which never
# runs FastAPI's lifespan events, but routes still need somewhere to hold
# strong references to their fire-and-forget audit-publish tasks.
app.state.background_tasks = set()
app.include_router(skills_router)
app.include_router(connections_router)
app.include_router(invoke_router)


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
