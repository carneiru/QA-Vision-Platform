# {{SERVICE_DESCRIPTION}}

Part of the QA Vision Platform (QEOS) – Platform Domain.

Provides CRUD operations for {{SERVICE_TITLE}}s (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/{{SERVICE_NAME}}s` – list {{SERVICE_NAME}}s
- `POST /api/v1/{{SERVICE_NAME}}s` – create {{SERVICE_NAME}}
- `GET /api/v1/{{SERVICE_NAME}}s/{id}` – get {{SERVICE_NAME}}
- `PUT /api/v1/{{SERVICE_NAME}}s/{id}` – update {{SERVICE_NAME}}
- `DELETE /api/v1/{{SERVICE_NAME}}s/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
