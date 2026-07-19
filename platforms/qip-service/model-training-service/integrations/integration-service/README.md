# Handles third-party integrations

Part of the QA Vision Platform (QEOS) – integrations Domain.

Provides CRUD operations for Integration Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/integration-services` – list integration-services
- `POST /api/v1/integration-services` – create integration-service
- `GET /api/v1/integration-services/{id}` – get integration-service
- `PUT /api/v1/integration-services/{id}` – update integration-service
- `DELETE /api/v1/integration-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
