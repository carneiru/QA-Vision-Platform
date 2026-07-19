from fastapi import FastAPI
from plugin_runtime_service.api.v1 import router as v1_router

app = FastAPI(
    title="Plugin Runtime Service",
    description="Service for managing plugin execution and runtime in QA Vision Platform",
    version="1.0.0"
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Plugin Runtime Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
