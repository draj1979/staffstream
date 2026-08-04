from fastapi import FastAPI

from .routers.memory import router as memory_router

app = FastAPI(title="Memory Service")
app.include_router(memory_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
