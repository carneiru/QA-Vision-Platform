from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.project.api.v1.api import api_router
from src.project.api.v1.endpoints import internal
from src.project.core.config import settings

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
# Service-to-service only: HTTP Basic, not routed by the gateway, not in the OpenAPI schema
app.include_router(internal.router, prefix="/internal/v1", include_in_schema=False)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
