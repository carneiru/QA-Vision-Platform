# Workflow Service

A microservice for designing and managing workflow definitions for test automation.

## Overview

The Workflow Service provides RESTful APIs for creating, editing, and managing workflow definitions and their individual steps. Workflows can be categorized, tagged, and versioned for easy organization and retrieval.

## Features

- Create, read, update, and delete workflows
- Create, read, update, and delete workflow steps
- Organize workflows by category and tags
- Version control for workflow definitions
- Flexible step configuration for different step types (action, validation, wait, loop, condition, etc.)

## API Endpoints

### Workflows
- `POST /api/v1/workflows/` - Create a new workflow
- `GET /api/v1/workflows/` - List all workflows (with pagination)
- `GET /api/v1/workflows/{workflow_id}` - Get a specific workflow
- `PUT /api/v1/workflows/{workflow_id}` - Update a workflow
- `DELETE /api/v1/workflows/{workflow_id}` - Delete a workflow
- `GET /api/v1/workflows/category/{category}` - Get workflows by category
- `GET /api/v1/workflows/tag/{tag}` - Get workflows by tag

### Steps
- `POST /api/v1/steps/` - Create a new step
- `GET /api/v1/steps/` - List all steps (with pagination)
- `GET /api/v1/steps/{step_id}` - Get a specific step
- `PUT /api/v1/steps/{step_id}` - Update a step
- `DELETE /api/v1/steps/{step_id}` - Delete a step
- `GET /api/v1/steps/workflow/{workflow_id}` - Get steps for a specific workflow
- `GET /api/v1/steps/type/{step_type}` - Get steps by type

## Technology Stack

- **Framework**: FastAPI
- **Language**: Python 3.9+
- **Database**: MongoDB
- **API Documentation**: Swagger UI (available at `/docs`)

## Setup and Installation

### Prerequisites
- Python 3.9+
- Docker and Docker Compose (for containerized deployment)
- MongoDB (for development)

### Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables (copy `.env.example` to `.env` and edit as needed)
4. Start the application:
   ```bash
   uvicorn main:app --reload
   ```

### Docker Deployment

1. Build and start the services:
   ```bash
   docker-compose up --build
   ```
2. The API will be available at `http://localhost:8000`

## Configuration

Environment variables can be configured in the `.env` file:
- `MONGODB_URL`: MongoDB connection string
- `APP_NAME`: Application name
- `APP_VERSION`: Application version
- `DEBUG`: Enable debug mode

## API Documentation

Once the application is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

Run the test suite:
```bash
pytest
```

## License

This project is licensed under the MIT License.