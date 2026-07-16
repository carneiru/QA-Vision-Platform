# Optimizes test execution and resource utilization

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Optimization Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/optimization-services` – list optimization-services
- `POST /api/v1/optimization-services` – create optimization-service
- `GET /api/v1/optimization-services/{id}` – get optimization-service
- `PUT /api/v1/optimization-services/{id}` – update optimization-service
- `DELETE /api/v1/optimization-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
