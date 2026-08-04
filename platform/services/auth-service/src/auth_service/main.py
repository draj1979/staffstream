from fastapi import FastAPI

from .routers.auth import router as auth_router

app = FastAPI(title="Auth Service")
app.include_router(auth_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
