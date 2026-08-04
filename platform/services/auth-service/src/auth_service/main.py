from fastapi import FastAPI, Response, status

from tenancy import check_db_ready

from . import db
from .routers.auth import router as auth_router

app = FastAPI(title="Auth Service")
app.include_router(auth_router)


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
