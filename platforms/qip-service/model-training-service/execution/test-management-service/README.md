# Test Management Service

## Overview
The Test Management Service is a microservice responsible for managing test cases, test suites, and test specifications in the QA AI Dashboard platform.

## Features
- Create, read, update, and delete test cases
- Create, read, update, and delete test suites
- Create, read, update, and delete test specifications
- Associate test cases with test suites and specifications
- Filter and paginate through test entities
- Tag-based categorization of test artifacts

## Technology Stack
- FastAPI - Modern, fast (high-performance), web framework for building APIs with Python 3.6+ based on standard Python type hints
- Motor - Async Python MongoDB driver
- MongoDB - NoSQL database
- Pydantic - Data validation and settings management using Python type hints
- Uvicorn - Lightning-fast ASGI server
- Docker - Containerization platform

## API Endpoints

### Test Cases
- `POST /api/v1/test-cases/` - Create a new test case
- `GET /api/v1/test-cases/` - List test cases (with pagination)
- `GET /api/v1/test-cases/{test_case_id}` - Get a specific test case
- `PUT /api/v1/test-cases/{test_case_id}` - Update a test case
- `DELETE /api/v1/test-cases/{test_case_id}` - Delete a test case

### Test Suites
- `POST /api/v1/test-suites/` - Create a new test suite
- `GET /api/v1/test-suites/` - List test suites (with pagination)
- `GET /api/v1/test-suites/{test_suite_id}` - Get a specific test suite
- `PUT /api/v1/test-suites/{test_suite_id}` - Update a test suite
- `DELETE /api/v1/test-suites/{test_suite_id}` - Delete a test suite

### Test Specifications
- `POST /api/v1/test-specifications/` - Create a new test specification
- `GET /api/v1/test-specifications/` - List test specifications (with pagination)
- `GET /api/v1/test-specifications/{test_spec_id}` - Get a specific test specification
- `PUT /api/v1/test-specifications/{test_spec_id}` - Update a test specification
- `DELETE /api/v1/test-specifications/{test_spec_id}` - Delete a test specification

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
- `MONGODB_DATABASE`: MongoDB database name (default: `test_management_db`)

## Testing
Run tests with: `pytest`

## License
MIT