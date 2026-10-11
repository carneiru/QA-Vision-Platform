from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from qeos_shared.metrics import install_metrics
from starlette.middleware.cors import CORSMiddleware

from src.ingestion.api.v1.api import api_router
from src.ingestion.core.config import settings
from src.ingestion.db.session import SessionLocal
from src.ingestion.utils import metrics
from src.ingestion.utils.job_metrics import JobHeartbeatCollector

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Ingestion's own registry, so the qav_* metrics keep their names on the same page (spec §3)
install_metrics(app, service="ingestion", registry=metrics.REGISTRY)
HEARTBEATS = JobHeartbeatCollector(SessionLocal)
metrics.REGISTRY.register(HEARTBEATS)


@app.exception_handler(RequestValidationError)
async def count_rejected_uploads(request: Request, exc: RequestValidationError):
    # Count 422s on the upload endpoint; every other route keeps FastAPI's default behaviour
    if request.url.path == f"{settings.API_V1_STR}/collect/runs":
        metrics.REJECTED.labels(reason="validation").inc()
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def health_check():
    return {"status": "healthy"}

