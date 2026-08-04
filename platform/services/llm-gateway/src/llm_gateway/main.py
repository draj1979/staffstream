from contextlib import asynccontextmanager

from fastapi import FastAPI

from events import RabbitMQPublisher

from .config import settings
from .gateway import build_default_gateway
from .routers.generate import router as generate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.publisher = RabbitMQPublisher(settings.rabbitmq_url)
    yield
    await app.state.publisher.close()


app = FastAPI(title="LLM Gateway", lifespan=lifespan)
app.state.gateway = build_default_gateway(anthropic_api_key=settings.anthropic_api_key)
# Not inside lifespan: tests drive the app via ASGITransport, which never
# runs FastAPI's lifespan events, but the /generate route still needs
# somewhere to hold strong references to its fire-and-forget publish tasks.
app.state.background_tasks = set()
app.include_router(generate_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    # No database of its own — ready as soon as the process is up.
    return {"status": "ready"}
