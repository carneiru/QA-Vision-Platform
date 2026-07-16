# Feature Store Service

A service for managing machine learning features with versioning, retrieval capabilities, and feature group management in the QA Vision Platform's AI Engine.

## Overview

The Feature Store Service provides a centralized repository for managing machine learning features, enabling data scientists and ML engineers to discover, share, and reuse features across different models and projects. It offers feature versioning, metadata management, and efficient feature retrieval capabilities.

## Features

### ✅ Fully Implemented
- **Feature Group Management**: Create, read, update, delete feature groups
- **Feature Management**: Create, read, update, delete features with versioning
- **Feature Versioning**: Track changes to features over time with version control
- **Feature Value Storage**: Store and retrieve feature values for entities
- **Batch Operations**: Efficient batch creation and retrieval of feature values
- **Feature Registration**: Register features with initial versions and group associations
- **Feature Retrieval**: Efficient retrieval of feature values for model training and inference
- **Feature Group Associations**: Manage relationships between features and feature groups
- **Health Checks**: Service health monitoring endpoints
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Database Configuration**: PostgreSQL connection settings
- **Feature Store Configuration**: TTL settings for feature values, batch sizes

### 📝 Planned Enhancements
- Feature drift detection and monitoring
- Feature usage analytics and lineage tracking
- Online serving capabilities for real-time feature retrieval
- Integration with feature validation and testing frameworks
- Advanced search and discovery capabilities
- Feature sharing and collaboration features

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/ai-engine/services/feature_store
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
- `APP_NAME`: Service name (default: "Feature Store Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for metadata and feature definitions)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "feature_store")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Feature Store Configuration
- `FEATURE_VALUE_TTL_DAYS`: Time-to-live for feature values in days (default: 365)
- `MAX_BATCH_SIZE`: Maximum batch size for feature operations (default: 1000)
- `FEATURE_VALUE_CACHE_TTL_SECONDS`: Cache TTL for feature values (default: 300)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Feature Group Management
- `POST /api/v1/feature-groups` - Create a new feature group
- `GET /api/v1/feature-groups` - List feature groups (with filtering and pagination)
- `GET /api/v1/feature-groups/{id}` - Get feature group by ID
- `GET /api/v1/feature-groups/name/{name}` - Get feature group by name
- `PUT /api/v1/feature-groups/{id}` - Update feature group
- `DELETE /api/v1/feature-groups/{id}` - Delete feature group

### Feature Management
- `POST /api/v1/features` - Create a new feature
- `GET /api/v1/features` - List features (with filtering and pagination)
- `GET /api/v1/features/{id}` - Get feature by ID
- `GET /api/v1/features/name/{name}` - Get feature by name
- `PUT /api/v1/features/{id}` - Update feature
- `DELETE /api/v1/features/{id}` - Delete feature

### Feature Versioning
- `POST /api/v1/features/{feature_id}/versions` - Create a new feature version
- `GET /api/v1/features/{feature_id}/versions` - List versions for a feature
- `GET /api/v1/features/{feature_id}/versions/{version_id}` - Get feature version by ID
- `GET /api/v1/features/{feature_id}/versions/{version_number}` - Get feature version by number
- `GET /api/v1/features/{feature_id}/versions/latest` - Get latest active version
- `PUT /api/v1/features/{feature_id}/versions/{version_id}` - Update feature version
- `DELETE /api/v1/features/{feature_id}/versions/{version_id}` - Delete feature version

### Feature Value Management
- `POST /api/v1/feature-values` - Create a new feature value
- `POST /api/v1/feature-values/batch` - Create multiple feature values in batch
- `GET /api/v1/feature-values/{id}` - Get feature value by ID
- `GET /api/v1/feature-values/entities/{entity_id}` - Get feature values for an entity
- `GET /api/v1/feature-values/latest/{entity_id}/{feature_version_id}` - Get latest feature value
- `POST /api/v1/feature-values/batch` - Get feature values for multiple entities and features
- `DELETE /api/v1/feature-values/entities/{entity_id}` - Delete feature values for an entity

### Feature Group Associations
- `POST /api/v1/feature-groups/{feature_group_id}/features/{feature_id}` - Add feature to group
- `DELETE /api/v1/feature-groups/{feature_group_id}/features/{feature_id}` - Remove feature from group
- `GET /api/v1/features/{feature_id}/groups` - Get groups for a feature
- `GET /api/v1/feature-groups/{feature_group_id}/features` - Get features in a group

### Feature Registration
- `POST /api/v1/features/register` - Register a new feature with initial version and group associations

### Feature Retrieval
- `POST /api/v1/feature-values/retrieve` - Retrieve feature values for multiple entities and features
- `GET /api/v1/feature-values/entities/{entity_id}/features` - Get features for a specific entity

## Request/Response Models

### Feature Group
- **Request**: `FeatureGroupCreate` (name, description, tags, is_active)
- **Response**: `FeatureGroup` (id, name, description, tags, is_active, created_at, updated_at)

### Feature
- **Request**: `FeatureCreate` (name, description, data_type, is_active)
- **Response**: `Feature` (id, name, description, data_type, is_active, created_at, updated_at)

### Feature Version
- **Request**: `FeatureVersionCreate` (feature_id, version_number, description, is_active)
- **Response**: `FeatureVersion` (id, feature_id, version_number, description, is_active, created_at, updated_at)

### Feature Value
- **Request**: `FeatureValueCreate` (entity_id, feature_version_id, timestamp, value)
- **Response**: `FeatureValue` (id, entity_id, feature_version_id, timestamp, value, created_at)

### Feature Registration
- **Request**: `FeatureRegistrationRequest` (feature_group_names, feature, version)
- **Response**: `FeatureRegistrationResponse` (feature, feature_version, feature_groups)

### Feature Retrieval
- **Request**: `FeatureRetrievalRequest` (entity_ids, feature_names, timestamp)
- **Response**: `BatchFeatureRetrievalResponse` (results: List[FeatureRetrievalResponse])
- **FeatureRetrievalResponse**: (entity_id, timestamp, features: Dict[str, Any])

## Dependencies

- **Authentication Service**: For user validation and tenant context
- **Organization Service**: For organization/tenant context
- **PostgreSQL**: Stores feature metadata, groups, versions, and relationships
- **Shared Libraries**: Common utilities, configuration, logging, and database connections
- **Shared Database**: Async database session management

## Event Contracts

### Events Published
- `feature.created.v1` - When a new feature is created
- `feature.updated.v1` - When a feature is updated
- `feature.version.created.v1` - When a new feature version is created
- `feature.value.stored.v1` - When feature values are stored
- `feature.registered.v1` - When a feature is registered with initial version and groups

### Events Consumed
- Currently, the feature store service does not consume events from other services
- Future enhancements may include consuming events from data ingestion pipelines

## Database Schema

### PostgreSQL Schema

#### feature_groups Table
- `id`: Integer (Primary Key)
- `name`: String (Unique)
- `description`: Text
- `tags`: JSON (for flexible tagging)
- `is_active`: Boolean
- `created_at`: Timestamp
- `updated_at`: Timestamp

#### features Table
- `id`: Integer (Primary Key)
- `name`: String (Unique)
- `description`: Text
- `data_type`: String (e.g., 'float', 'int', 'string', 'bool')
- `is_active`: Boolean
- `created_at`: Timestamp
- `updated_at`: Timestamp

#### feature_versions Table
- `id`: Integer (Primary Key)
- `feature_id`: Integer (Foreign Key to features)
- `version_number`: Integer
- `description`: Text
- `is_active`: Boolean
- `created_at`: Timestamp
- `updated_at`: Timestamp

#### feature_values Table
- `id`: Integer (Primary Key)
- `entity_id`: String (Identifier for the entity, e.g., user_id, product_id)
- `feature_version_id`: Integer (Foreign Key to feature_versions)
- `timestamp`: Timestamp (when the feature value was observed)
- `value`: JSON (flexible storage for any data type)
- `created_at`: Timestamp

#### feature_group_feature Table (Many-to-Many)
- `feature_group_id`: Integer (Foreign Key to feature_groups)
- `feature_id`: Integer (Foreign Key to features)
- `assigned_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (admin, data_scientist, ml_engineer, viewer)
- Tenant isolation ensuring users can only access features in their tenant
- Feature-level permissions for sensitive features

### Data Protection
- Feature metadata stored in PostgreSQL with standard security practices
- Feature values stored as JSONB with appropriate access controls
- TLS encryption for all data in transit
- Regular security scanning of stored feature metadata
- Audit logging for all feature access and modifications

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Data Access      │
│ (REST Endpoints)│    │ (Feature CRUD,   │    │ (PostgreSQL      │
│                 │    │  Versioning,     │    │  + Search)       │
└─────────────────┘    │  Retrieval,      │    └──────────────────┘
                       │  Associations)   │    ┌──────────────────┐
                       └──────────────────┘    │ External Services│
                                               │ (Auth, Org)      │
                                               └──────────────────┘
```

## Running Tests

```bash
# From the feature-store directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_feature_groups.py
pytest tests/test_features.py
pytest tests/test_feature_versions.py
pytest tests/test_feature_values.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Configure proper connection pooling and database sizing
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for PostgreSQL
- Configure audit logging for feature access (ML compliance)

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for PostgreSQL reporting queries
- Connection pooling for efficient database access
- Caching layer for frequently accessed feature values
- Batch processing optimizations for offline feature computation
- Horizontal scaling of API instances based on request volume

### Data Integrity & Consistency
- ACID transactions for feature metadata operations
- Eventual consistency model for feature value writes (acceptable for ML use cases)
- Unique constraints to prevent duplicate feature names within tenant
- Foreign key constraints to maintain referential integrity
- Regular data quality checks for feature values

## Maintenance

### Database Migrations
```bash
# Generate new migration after model changes
alembic revision --autogenerate -m "description"

# Apply pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
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

### Feature Store Maintenance
- **Regular**: Monitor feature usage and cleanup unused features/values
- **Quarterly**: Review feature schema and data types for relevance
- **Annual**: Review feature governance and access control policies
- **Continuous**: Monitor data quality and feature drift indicators

## Product Considerations

### Feature Types Supported
- **Numerical Features**: Continuous and discrete numerical values
- **Categorical Features**: String and enum values
- **Binary Features**: Boolean values
- **Complex Features**: JSON objects for structured data
- **Temporal Features**: Timestamp-based features

### Feature Sources Supported
- **Batch Computed**: Features computed periodically from batch jobs
- **Streaming Computed**: Features computed from real-time data streams
- **Manual Entry**: Features manually entered or updated
- **External Import**: Features imported from external systems

### Feature Lifecycle Stages
- **Development**: Features under active development and testing
- **Staging**: Features validated and ready for production testing
- **Production**: Features actively used in production models
- **Deprecated**: Features maintained for compatibility but discouraged for new use
- **Archived**: Features no longer used but retained for historical reference

### Quality Metrics
- Feature completeness (percentage of entities with values)
- Feature freshness (time since last update)
- Feature usage frequency (how often features are used in models)
- Feature stability (how often feature values or definitions change)