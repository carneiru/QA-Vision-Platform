from fastapi import FastAPI
from sdk_service.api.v1 import router as v1_router

app = FastAPI(
    title="SDK Service",
    description="Service for managing Software Development Kits in QA Vision Platform",
    version="1.0.0"
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "SDK Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
