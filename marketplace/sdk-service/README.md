# SDK Service

Service for managing Software Development Kits (SDKs) in QA Vision Platform.

## Overview

This service manages SDKs for the QA Vision Platform, providing version management, distribution, and compatibility information for developers building plugins and integrations.

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
2. Navigate to the sdk-service directory
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
   uvicorn main:app --reload --host 0.0.0.0 --port 8005
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

## API Endpoints

### Health
- `GET /` - Service health check
- `GET /health` - Detailed health status

### SDK Management
- `GET /api/v1/sdks` - List all SDKs
- `GET /api/v1/sdks/{sdk_id}` - Get specific SDK details
- `POST /api/v1/sdks` - Register a new SDK
- `PUT /api/v1/sdks/{sdk_id}` - Update SDK information
- `DELETE /api/v1/sdks/{sdk_id}` - Remove an SDK
- `GET /api/v1/sdks/{sdk_id}/versions` - Get all versions of an SDK
- `POST /api/v1/sdks/{sdk_id}/versions` - Add a new version to an SDK

### Version Management
- `GET /api/v1/versions/{version_id}` - Get specific version details
- `PUT /api/v1/versions/{version_id}` - Update version information
- `DELETE /api/v1/versions/{version_id}` - Delete a version
- `GET /api/v1/versions/{version_id}/files` - Get files for a version
- `POST /api/v1/versions/{version_id}/files` - Upload file for a version

### Compatibility
- `GET /api/v1/sdks/{sdk_id}/compatibility` - Get compatibility information
- `POST /api/v1/sdks/{sdk_id}/compatibility` - Update compatibility information

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

### Code Quality
```bash
# Code formatting
black .

# Type checking
mypy .

# Linting
flake8 .
