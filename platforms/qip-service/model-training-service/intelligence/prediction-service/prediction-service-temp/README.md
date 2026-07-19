# Model Management Service

A service for managing the lifecycle of machine learning models including registration, versioning, deployment, evaluation, and retirement in the QA Vision Platform's Intelligence domain.

## Overview

The Model Management Service provides comprehensive lifecycle management for machine learning models used across the QA Vision Platform. It enables data scientists and ML engineers to register, version, deploy, evaluate, and retire models while maintaining metadata, tracking performance, and ensuring proper governance.

## Features

### ✅ Fully Implemented
- **Model Registration**: Register new ML models with metadata and versioning
- **Model Versioning**: Manage multiple versions of the same model
- **Model Deployment**: Deploy specific model versions to serving endpoints
- **Model Evaluation**: Run automated evaluations against test datasets
- **Model Retirement**: Retire model versions when no longer needed
- **Model Metadata Management**: Store and retrieve model information, parameters, and performance metrics
- **Model Lineage Tracking**: Track model origins, training data, and transformations
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Model Storage Configuration**: Settings for where model artifacts are stored
- **Database Configuration**: PostgreSQL connection settings for model metadata
- **Evaluation Configuration**: Default datasets and metrics for model evaluation
- **Deployment Configuration**: Settings for model serving infrastructure
- **Monitoring Configuration**: Model performance monitoring and alerting thresholds

### 📝 Planned Enhancements
- Automated model retraining triggers based on performance drift
- A/B testing framework for model comparisons
- Model explainability and interpretability tools
- Integration with MLflow and other MLOps platforms
- Advanced model governance and compliance features
- Multi-armed bandit optimization for model selection
- Model serving optimization and autoscaling

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+ (for model metadata storage)
- Object storage (S3, MinIO, or similar) for model artifacts
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/prediction/prediction-service
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration (see Environment Variables section below)
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database setup**
   ```bash
   # Ensure PostgreSQL is running
   # Then apply migrations
   alembic upgrade head
   ```

5. **Run the application**
   ```bash
   # Development mode
   python main.py
   
   # API will be available at http://localhost:8000
   # API documentation:
   # - Swagger UI: http://localhost:8000/api/v1/docs
   # - ReDoc: http://localhost:8000/api/v1/redoc
   ```

### Docker Deployment

```bash
docker-compose up --build
```

## Environment Variables

Copy `.env.example` to `.env` and configure as needed:

### Application Settings
- `APP_NAME`: Service name (default: "Model Management Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for model metadata)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "model_registry")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Model Storage Configuration
- `MODEL_STORAGE_TYPE`: Storage type (s3, minio, local, gcs, azure)
- `MODEL_STORAGE_BUCKET`: Bucket/container name for model artifacts
- `MODEL_STORAGE_PATH`: Path within storage for model files
- `MODEL_STORAGE_ENDPOINT`: Endpoint for S3-compatible services (for MinIO)
- `MODEL_ACCESS_KEY`: Access key for storage authentication
- `MODEL_SECRET_KEY`: Secret key for storage authentication
- `MODEL_STORAGE_SECURE`: Use HTTPS for storage (default: true)

### Evaluation Configuration
- `DEFAULT_EVALUATION_DATASET`: Default dataset for model evaluation
- `EVALUATION_BATCH_SIZE`: Batch size for evaluation (default: 32)
- `EVALUATION_METRICS`: Default metrics to compute (accuracy, precision, recall, f1, auc)
- `EVALUATION_TIMEOUT_SECONDS`: Timeout for evaluation jobs (default: 3600)

### Deployment Configuration
- `MODEL_SERVING_PLATFORM`: Serving platform (kserve, seldon, triton, custom)
- `MODEL_SERVING_NAMESPACE`: Kubernetes namespace for model serving
- `MODEL_SERVING_TIMEOUT`: Timeout for deployment operations (default: 300)

### Monitoring Configuration
- `METRICS_COLLECTION_ENABLED`: Enable metrics collection (default: true)
- `METRICS_COLLECTION_INTERVAL`: Interval for collecting metrics (default: 60)
- `PERFORMANCE_ALERT_THRESHOLD`: Threshold for performance alerts (default: 0.05)
- `DRIFT_DETECTION_ENABLED`: Enable data drift detection (default: true)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Model Management
- `POST /api/v1/models` - Register new ML model
  - Body: `ModelRegistrationRequest` (name, description, framework, version, metadata)
- `GET /api/v1/models/{id}` - Get model details and metadata
  - Path param: `id` (model UUID)
- `GET /api/v1/models` - List/filter models with pagination
  - Query params: `name`, `framework`, `tags`, `created_after`, `created_before`, `limit`, `offset`
- `PUT /api/v1/models/{id}/version/{version}` - Deploy specific model version
  - Path params: `id` (model UUID), `version` (version string)
  - Body: `ModelDeploymentRequest` (environment, resources, config overrides)
- `POST /api/v1/models/{id}/evaluate` - Run model evaluation against test set
  - Path param: `id` (model UUID)
  - Body: `ModelEvaluationRequest` (dataset_id, metrics, parameters)
- `DELETE /api/v1/models/{id}` - Retire model version
  - Path param: `id` (model UUID)
  - Query param: `version` (optional, if not provided retires all versions)
- `GET /api/v1/models/{id}/versions` - List all versions of a model
  - Path param: `id` (model UUID)
- `GET /api/v1/models/{id}/version/{version}` - Get specific model version details
  - Path params: `id` (model UUID), `version` (version string)
- `POST /api/v1/models/{id}/version/{version}/promote` - Promote model to next stage
  - Path params: `id` (model UUID), `version` (version string)
  - Body: `ModelPromotionRequest` (target_stage, approval_notes)

### Model Metadata
- `GET /api/v1/models/{id}/metadata` - Get model metadata
- `PUT /api/v1/models/{id}/metadata` - Update model metadata
- `POST /api/v1/models/{id}/tags` - Add tags to model
- `DELETE /api/v1/models/{id}/tags/{tag}` - Remove tag from model

### Model Lineage
- `GET /api/v1/models/{id}/lineage` - Get model lineage (parents, children, derivatives)
- `POST /api/v1/models/{id}/lineage` - Add lineage relationship
- `/api/v1/models/{id}/lineage/{relation_id}` - Remove lineage relationship

## Request/Response Models

### Model Registration
- **Request**: `ModelRegistrationRequest` (name, description, framework, version, metadata, tags)
- **Response**: `Model` (id, name, description, framework, version, status, created_at, updated_at, tags)

### Model Details
- **Response**: `Model` (id, name, description, framework, version, status, created_at, updated_at, tags, current_version, versions)

### Model Version
- **Response**: `ModelVersion` (version, status, created_at, deployed_at, deployed_environment, metrics, artifacts_location, checksum)

### Model Deployment
- **Request**: `ModelDeploymentRequest` (environment, resources, config_overrides)
- **Response**: `ModelDeployment` (deployed_at, environment, version, status, endpoint_url, resources_used)

### Model Evaluation
- **Request**: `ModelEvaluationRequest` (dataset_id, metrics, parameters, async_flag)
- **Response**: `ModelEvaluationResponse` (evaluation_id, status, started_at, completed_at, results)

### Model Promotion
- **Request**: `ModelPromotionRequest` (target_stage, approval_notes, approver_id)
- **Response**: `ModelPromotionResponse` (previous_stage, new_stage, promoted_at, promoted_by)

## Dependencies

- **Authentication Service**: For user validation and permissions
- **Organization Service**: For organization/context isolation
- **Knowledge Service**: For storing model-related insights and recommendations
- **Execution Service**: For running model evaluations using test infrastructure
- **PostgreSQL**: Stores model metadata, versions, deployment info, and evaluation results
- **Object Storage (S3/MinIO)**: Stores model artifacts (weights, configurations, etc.)
- **Redis**: Caching layer for frequent model queries and pub/sub notifications
- **Model Serving Platform**: KServe, Seldon, Triton, or custom serving infrastructure
- **Monitoring System**: Prometheus/Grafana for model performance metrics
- **Shared Libraries**: Common utilities, configuration, logging

## Event Contracts

### Events Published
- `model.registered.v1` - When a new model is registered
- `model.version.created.v1` - When a new model version is created
- `model.deployed.v1` - When a model version is deployed
- `model.evaluation.completed.v1` - When model evaluation completes
- `model.retired.v1` - When a model version is retired
- `model.promoted.v1` - When a model version is promoted to a new stage

### Events Consumed
- `training.completed.v1` - From Training Service when model training completes
- `validation.completed.v1` - From Validation Service when model validation completes
- `feature.updated.v1` - From Feature Store when features are updated
- `dataset.registered.v1` - From Dataset Service when new datasets are registered
- `insight.generated.v1` - From Insight Generation Service for model improvement suggestions

## Database Schema

### PostgreSQL Schema

#### models Table
- `id`: UUID (Primary Key)
- `name`: String (Model name)
- `description`: Text (Model description)
- `framework`: String (ML framework: tensorflow, pytorch, scikit-learn, etc.)
- `tags`: JSONB (Array of string tags for categorization)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `created_by`: UUID (Foreign Key to users table)
- `updated_by`: UUID (Foreign Key to users table)

#### model_versions Table
- `id`: UUID (Primary Key)
- `model_id`: UUID (Foreign Key to models)
- `version`: String (Version identifier)
- `status`: String (training, validated, deployed, deprecated, retired, failed)
- `created_at`: Timestamp
- `deployed_at`: Timestamp (Nullable)
- `deployed_environment`: String (Nullable)
- `artifacts_location`: String (Path to model artifacts in object storage)
- `checksum`: String (SHA256 of model artifacts for integrity)
- `metadata`: JSONB (Model parameters, hyperparameters, training config)
- `metrics`: JSONB (Performance metrics from training/evaluation)
- `created_by`: UUID (Foreign Key to users table)

#### model_deployments Table
- `id`: UUID (Primary Key)
- `model_id`: UUID (Foreign Key to models)
- `version_id`: UUID (Foreign Key to model_versions)
- `environment`: String (staging, production, canary, etc.)
- `deployed_at`: Timestamp
- `deployed_by`: UUID (Foreign Key to users table)
- `endpoint_url`: String (URL where model is served)
- `resources`: JSONB (CPU, memory, GPU allocation)
- `status`: String (deploying, active, failed, stopped)
- `health_check_url`: String (Endpoint for health checks)

#### model_evaluations Table
- `id`: UUID (Primary Key)
- `model_id`: UUID (Foreign Key to models)
- `version_id`: UUID (Foreign Key to model_versions)
- `dataset_id`: String (Reference to evaluation dataset)
- `started_at`: Timestamp
- `completed_at`: Timestamp (Nullable)
- `status`: String (running, completed, failed, cancelled)
- `triggered_by`: UUID (Foreign Key to users table, nullable if automated)
- `parameters`: JSONB (Evaluation parameters)
- `results`: JSONB (Evaluation metrics and detailed results)
- `error_message`: Text (If evaluation failed)

#### model_lineage Table
- `id`: UUID (Primary Key)
- `parent_model_id`: UUID (Foreign Key to models)
- `child_model_id`: UUID (Foreign Key to models)
- `relationship_type`: String (derivative, ensemble, fine-tuned, etc.)
- `created_at`: Timestamp
- `created_by`: UUID (Foreign Key to users table)
- `description`: Text (Description of relationship)

## Security Implementation

### Authentication & Authorization
- JWT-based authentication with refresh token rotation
- Role-based access control (admin, ml_engineer, data_scientist, auditor, viewer)
- Tenant isolation ensuring users can only access models in their tenant
- Model-level permissions for sensitive models (proprietary or regulated models)
- Service-to-service authentication for internal communications

### Data Protection
- Model metadata stored in PostgreSQL with standard security practices
- Model artifacts stored in object storage with encryption at rest
- TLS encryption for all data in transit
- Regular security scanning of stored model metadata and artifacts
- Audit logging for all model access, registration, deployment, and evaluation
- Model version immutability (once created, versions cannot be modified)
- Access controls on model deployment and promotion operations

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Object Storage**: S3/MinIO client libraries
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Data Access &    │
│ (REST Endpoints)│    │ (Model Registration,│    │ Storage          │
│                 │    │  Versioning,      │    │ (PostgreSQL      │
└─────────────────┘    │  Deployment, Eval)│    │  + Object Store) │
                       └──────────────────┘    └──────────────────┘
                                ▲                   ▲
                                │                   │
                       ┌──────────────────┐    ┌──────────────────┐
                       │ External Services│    │ Internal Events  │
                       │ (KServe, MLflow) │    │ (Kafka/Pulsar)   │
                       └──────────────────┘    └──────────────────┘
```

### Core Components Implementation

1. **Model Registry Service**: Handles model registration, versioning, and metadata management
2. **Model Deployment Service**: Manages model deployment to serving infrastructure
3. **Model Evaluation Service**: Orchestrates model evaluation against test datasets
4. **Model Lifecycle Service**: Handles model promotion, retirement, and archival
5. **Event Processing Service**: Consumes and produces domain events for integration
6. **Storage Abstraction Layer**: Unified interface for different object storage backends

#### Model Registration Flow
1. User submits model registration request with metadata
2. Service validates input and checks for duplicate names within tenant
3. Model record created in PostgreSQL with initial version
4. Model artifacts uploaded to object storage
5. Model version record created with storage location and checksum
6. `model.registered.v1` event published
7. Model record returned to user with ID and version info

#### Model Deployment Flow
1. User requests deployment of specific model version to environment
2. Service validates model exists and version is in deployable state
3. Deployment request sent to model serving platform (KServe, Seldon, etc.)
4. Deployment status tracked and updated in database
5. Service endpoint retrieved and stored
6. `model.deployed.v1` event published
7. Deployment confirmation returned to user

#### Model Evaluation Flow
1. User submits evaluation request for model version
2. Service validates model exists and version is available
3. Evaluation job created and dispatched to processing system
4. Test dataset retrieved from training/evaluation output: Model evaluation process runs against test dataset
5. Metrics calculated and results stored
6. `model.evaluation.completed.v1` event published
7. Results returned to user (immediately if sync, or via callback if async)

## Running Tests

```bash
# From the model-management-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_model_registration.py
pytest/tests/test_model_deployment.py
pytest/tests/test_model_evaluation.py
pytest/tests/test_model_lifecycle.py
pytest/tests/test_model_lineage.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.) with read replicas
- Use managed object storage (AWS S3, Google Cloud Storage, Azure Blob Storage)
- Configure proper connection pooling and database sizing
- Use managed Kafka service (Confluent Cloud, AWS MSK, etc.) for event streaming
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for PostgreSQL
- Configure audit logging for model access (ML compliance, GDPR, etc.)
- Implement model signing and verification for integrity

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for PostgreSQL reporting queries
- Horizontal scaling of model evaluation workers
- Object storage naturally scales for model artifacts
- Kubernetes-based model serving for automatic scaling
- GPU node pools for accelerated model inference
- Distributed training integration for large model retraining
- Model serving optimization (TensorRT, TorchScript, ONNX Runtime)

### Data Integrity & Consistency
- ACID transactions for model metadata operations
- Immutable model artifacts with checksum verification
- Eventual consistency model acceptable for most model management operations
- Model version immutability prevents accidental changes
- Referential integrity enforced via foreign key constraints
- Regular data validation jobs for metadata consistency
- Backup and disaster recovery procedures for model registry
- Data retention policies for different types of model metadata

## Maintenance

### Database Maintenance
```bash
# Vacuum and analyze tables periodically
VACUUM ANALYZE models;
VACUUM ANALYZE model_versions;
VACUUM ANALYZE model_deployments;
VACUUM ANALYZE model_evaluations;

# Check for orphaned records
DELETE FROM model_versions WHERE model_id NOT IN (SELECT id FROM models);
DELETE FROM model_deployments WHERE model_id NOT IN (SELECT id FROM models);
DELETE FROM model_evaluations WHERE model_id NOT IN (SELECT id FROM models);
DELETE FROM model_lineage WHERE parent_model_id NOT IN (SELECT id FROM models) 
   OR child_model_id NOT IN (SELECT id FROM models);

# Update index statistics
REINDEX TABLE models;
REINDEX TABLE model_versions;
REINDEX TABLE model_deployments;
REINDEX TABLE model_evaluations;
REINDEX TABLE model_lineage;
```

### Dependency Updates
```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install -U package-name

# Update all packages (review changes first!)
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U
```

### Model Management Service Maintenance
- **Hourly**: Monitor model deployment health and serving metrics
- **Daily**: Review model registration and deployment activities
- **Weekly**: Audit model usage and identify underutilized models
- **Monthly**: Review model performance trends and drift indicators
- **Quarterly**: Evaluate and update model governance policies
- **Annually**: Assess storage costs and implement archival strategies
- **Continuous**: Monitor model serving performance and error rates
- **Continuous**: Track model evaluation queue depths and processing times

## Product Considerations

### Model Lifecycle Stages
- **Development**: Model is being trained and experimented with
- **Validation**: Model has been validated and is ready for testing
- **Staging**: Model is deployed to staging environment for final testing
- **Production**: Model is actively serving predictions in production
- **Deprecated**: Model is superseded but maintained for backward compatibility
- **Retired**: Model is no longer serving and marked for archival
- **Archived**: Model moved to long-term storage for historical/reference

### Model Types Supported
- **Traditional ML**: Scikit-learn, XGBoost, LightGBM, CatBoost models
- **Deep Learning**: TensorFlow, PyTorch, Keras models
- **Custom Models**: MLflow models, ONNX models, PMML models
- **Pipeline Models**: Scikit-learn pipelines, TensorFlow Serving pipelines
- **Ensemble Models**: Voting, stacking, blending ensembles
- **Time Series Models**: Prophet, ARIMA, LSTM-based time series models

### Model Artifact Support
- **Serialized Models**: Pickle, joblib, H5, SavedModel, TorchScript
- **Model Formats**: ONNX, PMML, TensorFlow SavedModel, PyTorch TorchScript
- **Container Models**: Docker images with model serving baked in
- **Model Packages**: MLflow models, SageMaker models, Azure ML models
- **Config-Based Models**: Rule-based systems, configuration-driven models

### Model Governance Features
- **Model Card Generation**: Automated creation of model documentation
- **Datasheet Integration**: Linking models to their training data sheets
- **Risk Assessment**: Automated model risk scoring based on usage and impact
- **Approval Workflows**: Configurable approval processes for promotion
- **Access Logging**: Detailed audit trails for all model interactions
- **Version Comparison**: Tools to compare performance across model versions
- **Impact Analysis**: Understanding effects of model changes on downstream systems