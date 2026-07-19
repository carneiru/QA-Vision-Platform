# Plugin Runtime Service

Service for managing plugin execution and runtime in the QA Vision Platform.

## Architecture

This service follows Domain-Driven Design (DDD) principles with the following layers:
- `api`: REST API endpoints using FastAPI
- `application`: Application services and use cases
- `domain`: Core business logic and entities
- `infrastructure`: External service integrations
- `persistence`: Data access layer
- `events`: Event handling and publishing
- `contracts`: Data transfer objects and interfaces
- `config`: Configuration management
- `tests`: Unit and integration tests

## Getting Started

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- MongoDB
- Kafka (optional, for event streaming)

### Installation

1. Clone the repository
2. Navigate to the plugin-runtime-service directory
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Service

#### Directly with Python
```bash
uvicorn main:app --host 0.0.0.0 --port 8003
```

#### Using Docker
```bash
docker build -t plugin-runtime-service .
docker run -p 8003:8003 plugin-runtime-service
```

#### Using Docker Compose (with dependencies)
```bash
docker-compose up
```

The service will be available at http://localhost:8003

## API Endpoints

### Health
- `GET /health` - Health check
- `GET /` - Root endpoint

### Plugins
- `GET /api/v1/plugins` - List deployed plugins
- `GET /api/v1/plugins/{plugin_id}` - Get plugin details
- `POST /api/v1/plugins/deploy` - Deploy a plugin
- `POST /api/v1/plugins/{plugin_id}/start` - Start a plugin
- `POST /api/v1/plugins/{plugin_id}/stop` - Stop a plugin
- `DELETE /api/v1/plugins/{plugin_id}/api/v1/plugins/Unundeploy a plugin
- `GET /api/v1/plugins/{plugin_id}/logs` - Get plugin
- GET /api/v1/plugins/{plugin_id}/metrics - Get plugin performance

### Configuration
MONGONGODB_URL:`, or by editin
- Deleting the volume if using Docker Compose:
  ```bash
  docker-compose down -v
  ```

## License

MIT License
