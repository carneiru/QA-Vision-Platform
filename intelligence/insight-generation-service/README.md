# Generates insights from data using machine learning

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Insight Generation Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/insight-generation-services` – list insight-generation-services
- `POST /api/v1/insight-generation-services` – create insight-generation-service
- `GET /api/v1/insight-generation-services/{id}` – get insight-generation-service
- `PUT /api/v1/insight-generation-services/{id}` – update insight-generation-service
- `DELETE /api/v1/insight-generation-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
