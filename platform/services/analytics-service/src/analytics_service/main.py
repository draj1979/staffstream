from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from tenancy import check_db_ready

from . import db
from .consumer import start_consumers, stop_consumers
from .routers.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.consumer_tasks = start_consumers()
    yield
    await stop_consumers(app.state.consumer_tasks)


app = FastAPI(title="Analytics Service", lifespan=lifespan)
app.include_router(analytics_router)


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
