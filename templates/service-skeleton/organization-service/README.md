# Organization Service

Part of QEOS – Platform Domain.

Provides CRUD operations for Organizations (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/organizations` – list organizations
- `POST /api/v1/organizations` – create organization
- `GET /api/v1/organizations/{id}` – get organization
- `PUT /api/v1/organizations/{id}` – update organization
- `DELETE /api/v1/organizations/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
