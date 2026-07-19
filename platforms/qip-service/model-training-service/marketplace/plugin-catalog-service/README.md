# Plugin Catalog Service

Service for managing plugin catalog in QA Vision Platform.

## Overview

This service manages the plugin catalog for the QA Vision Platform, providing CRUD operations for plugins, categories, tags, and compatibility information.

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
2. Navigate to the plugin-catalog-service directory
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the required infrastructure:
   ```bash
   docker-compose up -d mongodb kafka
   ```
5. Configure environment variables (see `.env.example`)
5. Start the service:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Deployment

```bash
docker-compose up --build
```

## API Endpoints

### Plugins
- `GET /api/v1/plugins` - Get all plugins
- `GET /api/v1/plugins/{plugin_id}` - Get plugin by ID
- `POST /api/v1/plugins` - Create a new plugin
- `PUT /api/v1/plugins/{plugin_id}` - Update a plugin
- `DELETE /api/v1/plugins/{plugin_id}` - Delete a plugin

### Categories
- `GET /api/v1/categories` - Get all categories
- `POST /api/v1/categories` - Create a new category

### Tags
- `GET /api/v1/tags` - Get all tags
- `POST /api/v1/tags` - Create a new tag

### Health
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint

## Environment Variables

- `MONGODB_URL`: MongoDB connection string (default: mongodb://localhost:27017)
- `DATABASE_NAME`: MongoDB database name (default: plugin_catalog)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (optional)
- `ENVIRONMENT`: Environment name (development/staging/production)

## Testing

Run tests with:
```bash
pytest
```

## License

MIT License
