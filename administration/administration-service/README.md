# Handles system administration, configuration, and tenant-level settings

Part of the QA Vision Platform (QEOS) – administration Domain.

Provides CRUD operations for Administration Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/administration-services` – list administration-services
- `POST /api/v1/administration-services` – create administration-service
- `GET /api/v1/administration-services/{id}` – get administration-service
- `PUT /api/v1/administration-services/{id}` – update administration-service
- `DELETE /api/v1/administration-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
