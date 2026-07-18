# Model Training Service

This service provides model training, evaluation, and lifecycle management capabilities for the QA AI Dashboard platform.

## Features

- Model registration and versioning
- Automated model training with hyperparameter tuning
- Model evaluation with metrics calculation
- Model deployment and retirement
- Model lifecycle management
- Integration with Kafka for event-driven architecture

## API Endpoints

### Models

- `POST /models/` - Register a new model
- `GET /models/` - List all models (with filtering)
- `GET /models/{model_id}` - Get a specific model
- `PUT /models/{model_id}` - Update a model
- `DELETE /models/{model_id}` - Delete a model

### Training & Evaluation

- `POST /models/{model_id}/train` - Start model training
- `POST /models/{model_id}/evaluate` - Start model evaluation
- `GET /models/{model_id}/evaluations` - Get model evaluations

### Deployment

- `POST /models/{model_id}/deploy` - Deploy a model
- `POST /models/{model_id}/retire` - Retire a model
- `GET /models/{model_id}/versions` - Get model versions

## Architecture

This service follows a microservice architecture with:

- **API Layer**: FastAPI endpoints
- **Service Layer**: Business logic
- **Data Layer**: SQLAlchemy ORM with PostgreSQL
- **Core Components**: Model training and evaluation engines
- **Configuration**: Pydantic-based settings management

## Configuration

Configuration is managed through environment variables or a `.env` file:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string (for caching)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses
- `MODEL_STORAGE_PATH`: Path for storing model artifacts
- `SECRET_KEY`: Secret key for JWT tokens
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time

## Running the Service

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the service
uvicorn src.model_training.main:app --reload
```

### Production (Docker)

```bash
# Build the image
docker build -t model-training-service .

# Run the container
docker run -p 8000:8000 model-training-service
```

## Database Migrations

This service uses Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Testing

```bash
# Run tests
pytest
```

## License

This service is part of the QA AI Dashboard platform.