from contextlib import asynccontextmanager

from fastapi import FastAPI

from events import RabbitMQPublisher

from .config import settings
from .routers.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.publisher = RabbitMQPublisher(settings.rabbitmq_url)
    yield
    await app.state.publisher.close()


app = FastAPI(title="OpenClaw Runtime", lifespan=lifespan)
# Not inside lifespan: tests drive the app via ASGITransport, which never
# runs FastAPI's lifespan events, but /chat still needs somewhere to hold
# strong references to its fire-and-forget publish tasks.
app.state.background_tasks = set()
app.include_router(chat_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    # No database of its own — ready as soon as the process is up.
    return {"status": "ready"}
