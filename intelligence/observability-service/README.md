# Handles metrics, tracing, logging, and alerting

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Observability Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/observability-services` – list observability-services
- `POST /api/v1/observability-services` – create observability-service
- `GET /api/v1/observability-services/{id}` – get observability-service
- `PUT /api/v1/observability-services/{id}` – update observability-service
- `DELETE /api/v1/observability-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
