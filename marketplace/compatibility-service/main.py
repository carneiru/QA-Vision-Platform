from fastapi import FastAPI
from api.v1 import router as v1_router

app = FastAPI(
    title="Compatibility Service",
    description="Service for managing plugin compatibility in QA Vision Platform",
    version="1.0.0"
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Compatibility Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    return {"status": "ok", "metrics": {}}
