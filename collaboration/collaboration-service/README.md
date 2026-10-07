# Manages team collaboration features: comments, notifications, file sharing, and real-time communication

Part of QEOS – collaboration Domain.

Provides CRUD operations for Collaboration Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/collaboration-services` – list collaboration-services
- `POST /api/v1/collaboration-services` – create collaboration-service
- `GET /api/v1/collaboration-services/{id}` – get collaboration-service
- `PUT /api/v1/collaboration-services/{id}` – update collaboration-service
- `DELETE /api/v1/collaboration-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
