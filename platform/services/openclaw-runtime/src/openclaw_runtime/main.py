from fastapi import FastAPI

from .routers.chat import router as chat_router

app = FastAPI(title="OpenClaw Runtime")
app.include_router(chat_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    # No database of its own — ready as soon as the process is up.
    return {"status": "ready"}
