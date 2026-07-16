# Test Execution Service

## Overview
The Test Execution Service is a microservice responsible for orchestrating test execution, managing test runs, and collecting results in the QA AI Dashboard platform.

## Features
- Create, read, update, and delete test runs
- Create, read, update, and delete test results
- Execute test runs (trigger test execution)
- Retrieve test results by test run or test case
- Filter and paginate through test execution entities
- Tag-based categorization of test runs and results

## Technology Stack
- FastAPI - Modern, fast (high-performance), web framework for building APIs with Python 3.6+ based on standard Python type hints
- Motor - Async Python MongoDB driver
- MongoDB - NoSQL database
- Pydantic - Data validation and settings management using Python type hints
- Uvicorn - Lightning-fast ASGI server
- Docker - Containerization platform

## API Endpoints

### Test Runs
- `POST /api/v1/test-runs/` - Create a new test run
- `GET /api/v1/test-runs/` - List test runs (with pagination)
- `GET /api/v1/test-runs/{test_run_id}` - Get a specific test run
- `PUT /api/v1/test-runs/{test_run_id}` - Update a test run
- `DELETE /api/v1/test-runs/{test_run_id}` - Delete a test run
- `POST /api/v1/test-runs/{test_run_id}/execute` - Execute a test run
- `GET /api/v1/test-runs/{test_run_id}/results` - Get all results for a test run

### Test Results
- `POST /api/v1/test-results/` - Create a new test result
- `GET /api/v1/test-results/` - List test results (with pagination)
- `GET /api/v1/test-results/{test_result_id}` - Get a specific test result
- `PUT /api/v1/test-results/{test_result_id}` - Update a test result
- `DELETE /api/v1/test-results/{test_result_id}` - Delete a test result
- `GET /api/v1/test-results/run/{test_run_id}` - Get all test results for a specific test run

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
- `MONGODB_DATABASE`: MongoDB database name (default: `test_execution_db`)

## Testing
Run tests with: `pytest`

## License
MIT