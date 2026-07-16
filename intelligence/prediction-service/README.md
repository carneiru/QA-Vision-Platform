# Provides predictive analytics and forecasting

Part of the QA Vision Platform (QEOS) – intelligence Domain.

Provides CRUD operations for Prediction Services (tenants) and related metadata.

## API

- `GET /health` – health check
- `GET /api/v1/prediction-services` – list prediction-services
- `POST /api/v1/prediction-services` – create prediction-service
- `GET /api/v1/prediction-services/{id}` – get prediction-service
- `PUT /api/v1/prediction-services/{id}` – update prediction-service
- `DELETE /api/v1/prediction-services/{id}` – soft delete

## Configuration

See `.env.example` for expected environment variables.

## Build & Run

```bash
docker build -t org-service .
docker run -p 8000:8000 --env-file .env org-service
```
