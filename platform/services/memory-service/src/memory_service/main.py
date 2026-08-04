from fastapi import FastAPI, Response, status

from tenancy import check_db_ready

from . import db
from .routers.memory import router as memory_router

app = FastAPI(title="Memory Service")
app.include_router(memory_router)


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
