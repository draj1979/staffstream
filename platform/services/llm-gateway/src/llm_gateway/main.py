from fastapi import FastAPI

from .config import settings
from .gateway import build_default_gateway
from .routers.generate import router as generate_router

app = FastAPI(title="LLM Gateway")
app.state.gateway = build_default_gateway(anthropic_api_key=settings.anthropic_api_key)
app.include_router(generate_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
