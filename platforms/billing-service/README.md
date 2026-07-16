# Handles subscriptions, billing, invoicing, and payment processing

Part of the QA Vision Platform (QEOS) – platforms Domain.

Provides CRUD operations for Billing Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/billing-services` – list billing-services
- `POST /api/v1/billing-services` – create billing-service
- `GET /api/v1/billing-services/{id}` – get billing-service
- `PUT /api/v1/billing-services/{id}` – update billing-service
- `DELETE /api/v1/billing-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
