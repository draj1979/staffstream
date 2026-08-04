from fastapi import FastAPI

from .routers.employees import router as employees_router

app = FastAPI(title="Employee Service")
app.include_router(employees_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
