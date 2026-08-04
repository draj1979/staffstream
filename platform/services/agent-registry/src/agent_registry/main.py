from fastapi import FastAPI

from .routers.agents import router as agents_router

app = FastAPI(title="Agent Registry")
app.include_router(agents_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
