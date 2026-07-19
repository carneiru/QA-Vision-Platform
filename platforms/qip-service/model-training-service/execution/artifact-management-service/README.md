# Artifact Management Service

## Overview
The Artifact Management Service is a microservice responsible for handling storage, retrieval, and management of test artifacts in the QA AI Dashboard platform.

## Features
- Upload, retrieve, update, and delete test artifacts (logs, screenshots, videos, reports, etc.)
- Organize artifacts into collections (test runs, builds, releases, etc.)
- Metadata management for artifacts
- Tag-based categorization and search
- Storage usage tracking per collection
- Artifact type

Collection

## Technology Stack
- FastAPI - Modern, fast (high-performance), web framework for building APIs with Python 3.6+ based on standard Python type hints
- Motor - Async Python MongoDB driver
- MongoDB - NoSQL database
- Pydantic - Data validation and settings management using Python type hints
- Uvicorn - Lightning-fast ASGI server
- Docker - Containerization platform

## API Endpoints

### Artifacts
- `POST /api/v1/artifacts/` - Upload a new artifact
- `GET /api/v1/artifacts/` - List artifacts (with pagination)
- `GET /api/v1/artifacts/{artifact_id}` - Get a specific artifact
- `PUT /api/v1/artifacts/{artifact_id}` - Update an artifact
- `DELETE /api/v1/artifacts/{artifact_id}` - Delete an artifact
- `GET /api/v1/artifacts/collection/{collection_id}` - Get all artifacts for a collection
- `GET /api/v1/artifacts/type/{artifact_type}` - Get all artifacts of a specific type

### Collections
- `POST /api/v1/collections/` - Create a new collection
- `GET /api/v1/collections/` - List collections (with pagination)
- `GET /api/v1/collections/{collection_id}` - Get a specific collection
- `PUT /api/v1/collections/{collection_id}` - Update a collection
- `DELETE /api/v1/collections/{collection_id}` - Delete a collection
- `GET /api/v1/collections/type/{collection_type}` - Get all collections of a specific type

## Setup and Installation

### Prerequisites
- Python 3.9+
- MongoDB 4.4+
- Docker (optional, for containerized deployment)

### Local Development
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables (see `.env.example`)
4. Run the application: `python main.py`
5. Access the API documentation at `http://localhost:8000/docs`

### Docker Deployment
1. Build and run: `docker-compose up --build`
2. Access the API documentation at `http://localhost:8000/docs`

## Environment Variables
- `MONGODB_URL`: MongoDB connection string (default: `mongodb://localhost:27017`)
- `MONGODB_DATABASE`: MongoDB database name (default: `artifact_management_db`)

## Testing
Run tests with: `pytest`

## License
MIT