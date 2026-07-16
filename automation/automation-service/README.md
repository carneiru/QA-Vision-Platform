# Manages workflow automation and orchestration

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Automation Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/automation-services` – list automation-services
- `POST /api/v1/automation-services` – create automation-service
- `GET /api/v1/automation-services/{id}` – get automation-service
- `PUT /api/v1/automation-services/{id}` – update automation-service
- `DELETE /api/v1/automation-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
