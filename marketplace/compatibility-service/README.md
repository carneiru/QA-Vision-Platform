# Compatibility Service

Service for managing plugin compatibility in QA Vision Platform.

## Overview

This service manages plugin compatibility checks for the QA Vision Platform, ensuring that plugins are compatible with specific versions of the platform and with each other.

## Architecture

This service follows Domain-Driven Design (DDD) principles with the following structure:
- `api`: API layer with FastAPI endpoints
- `application`: Application services and use cases
- `domain`: Domain entities, value objects, and repositories
- `infrastructure`: External service integrations
- `persistence`: Database models and repositories
- `events`: Domain events and event handlers
- `contracts`: Data transfer objects and API contracts
- `config`: Configuration management

## Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose (for local development)
- MongoDB
- Apache Kafka (optional, for event-driven architecture)

### Local Development

1. Clone the repository
2. Navigate to the compatibility-service directory
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the required infrastructure:
   ```bash
   docker-compose up -d mongodb kafka
   ```
5. Configure environment variables (see `.env.example`)
6. Start the service:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

## API Endpoints

### Health Check
- `GET /` - Service health check
- `GET /health` - Detailed health status

### Compatibility Management
- `GET /api/v1/compatibility` - List all compatibility records
- `GET /api/v1/compatibility/{rule_id}` - Get specific compatibility rule
- `POST /api/v1/compatibility` - Create new compatibility rule
- `PUT /api/v1/compatibility/{rule_id}` - Update compatibility rule
- `DELETE /api/v1/compatibility/{rule_id}` - Delete compatibility rule

### Compatibility Checking
- `POST /api/v1/check` - Check plugin compatibility
- `POST /api/v1/check/batch` - Batch compatibility checking

## Environment Variables

- `MONGODB_URL`: MongoDB connection string
- `DATABASE_NAME`: Name of the MongoDB database
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (optional)
- `ENVIRONMENT`: Deployment environment (development, staging, production)

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
```

### Type Checking
```bash
mypy .
```
