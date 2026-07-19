# Provides analytics capabilities including metrics, trends, predictions, and reporting

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Analytics Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/analytics-services` – list analytics-services
- `POST /api/v1/analytics-services` – create analytics-service
- `GET /api/v1/analytics-services/{id}` – get analytics-service
- `PUT /api/v1/analytics-services/{id}` – update analytics-service
- `DELETE /api/v1/analytics-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
