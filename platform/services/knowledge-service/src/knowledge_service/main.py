from fastapi import FastAPI, Response, status

from tenancy import check_db_ready

from . import db
from .config import settings
from .providers.voyage import VoyageEmbedder
from .routers.documents import router as documents_router

app = FastAPI(title="Knowledge Service")
app.state.embedder = VoyageEmbedder(api_key=settings.voyage_api_key)
app.include_router(documents_router)


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
