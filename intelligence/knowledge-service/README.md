# Provides knowledge base and search capabilities

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Knowledge Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/knowledge-services` – list knowledge-services
- `POST /api/v1/knowledge-services` – create knowledge-service
- `GET /api/v1/knowledge-services/{id}` – get knowledge-service
- `PUT /api/v1/knowledge-services/{id}` – update knowledge-service
- `DELETE /api/v1/knowledge-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
