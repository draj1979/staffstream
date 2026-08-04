from fastapi import FastAPI

from .config import settings
from .providers.voyage import VoyageEmbedder
from .routers.documents import router as documents_router

app = FastAPI(title="Knowledge Service")
app.state.embedder = VoyageEmbedder(api_key=settings.voyage_api_key)
app.include_router(documents_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
