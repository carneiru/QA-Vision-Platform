# Handles data ingestion, transformation, and enrichment

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Processing Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/processing-services` – list processing-services
- `POST /api/v1/processing-services` – create processing-service
- `GET /api/v1/processing-services/{id}` – get processing-service
- `PUT /api/v1/processing-services/{id}` – update processing-service
- `DELETE /api/v1/processing-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
