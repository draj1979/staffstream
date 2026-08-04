from fastapi import FastAPI

from .routers.tenants import router as tenants_router

app = FastAPI(title="Tenant Service")
app.include_router(tenants_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
