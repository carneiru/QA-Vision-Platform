from fastapi import FastAPI
from plugin_catalog_service.api.v1 import router as v1_router

app = FastAPI(
    title="Plugin Catalog Service",
    description="Service for managing plugin catalog in QA Vision Platform",
    version="1.0.0"
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Plugin Catalog Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
