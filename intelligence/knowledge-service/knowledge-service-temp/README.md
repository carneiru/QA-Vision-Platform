# Knowledge Management Service

A service for managing knowledge objects, insights, patterns, and recommendations in the QA Vision Platform's Quality Intelligence Platform (QIP).

## Overview

The Knowledge Management Service is responsible for the creation, storage, retrieval, validation, and lifecycle management of knowledge objects within the QA Vision Platform. It serves as the central repository for all intelligence-derived knowledge including insights, patterns, recommendations, facts, and metrics.

## Features

### ✅ Fully Implemented
- **Knowledge Object CRUD**: Create, read, update, delete knowledge objects
- **Flexible Schema Support**: JSON-based content with validation
- **Versioning**: Automatic version tracking for knowledge objects
- **Relationship Management**: Create and query relationships between knowledge objects
- **Validation Workflow**: Automated confidence scoring + optional human review
- **Knowledge Lifecycle**: Creation, validation, enrichment, publication, decay, archival
- **Search & Query**: Full-text search and filtered queries on knowledge objects
- **Tagging System**: Flexible tagging for categorization and filtering
- **Source Tracking**: Track knowledge origin (system, human, external, ML)
- **Event Publishing**: Domain events for knowledge lifecycle changes
- **Multi-tenancy**: Tenant-aware knowledge isolation
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Knowledge Retention Policies**: Configuration for knowledge decay and archival
- **Validation Thresholds**: Settings for automated confidence scoring
- **Relationship Types**: Configuration of allowed knowledge relationship types

### 📝 Planned Enhancements
- Advanced knowledge graph capabilities
- Machine learning-assisted knowledge discovery
- Natural language processing for knowledge extraction
- Collaborative knowledge editing
- Knowledge usage analytics and recommendations
- Integration with external knowledge bases (Wikipedia, domain-specific ontologies)
- Knowledge federation and sharing capabilities

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- MongoDB 7.0 (for flexible knowledge object storage)
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/knowledge/knowledge-service
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
   # Ensure PostgreSQL and MongoDB are running
   # Then apply migrations
   alembic upgrade head
   ```

5. **Run the application**
   ```bash
   # Development mode
   python src/knowledge/main.py
   
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
- `APP_NAME`: Service name (default: "Knowledge Management Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for metadata, relationships, tenancy)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "knowledge_db")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

#### MongoDB (for knowledge object content)
- `MONGODB_SERVER`: MongoDB host (default: "localhost")
- `MONGODB_PORT`: MongoDB port (default: 27017)
- `MONGODB_DB`: Database name (default: "knowledge_obj")
- **OR** `MONGODB_URI`: Full MongoDB connection string

### Knowledge Lifecycle Configuration
- `KNOWLEDGE_DEFAULT_VALIDITY_DAYS`: Default validity period in days (default: 365)
- `KNOWLEDGE_DECAY_ENABLED`: Enable automatic confidence decay (default: true)
- `KNOWLEDGE_DECAY_RATE_DAILY`: Daily confidence decay rate (default: 0.001 = 0.1%)
- `KNOWLEDGE_ARCHIVAL_DAYS_AFTER_EXPIRY`: Days after expiry to archive (default: 30)
- `KNOWLEDGE_MIN_CONFIDENCE_FOR_PUBLICATION`: Minimum confidence to publish (default: 0.7)

### Validation Configuration
- `VALIDATION_AUTO_SCORE_ENABLED`: Enable automated confidence scoring (default: true)
- `VALIDATION_HUMAN_REVIEW_THRESHOLD`: Confidence below which human review is required (default: 0.4)
- `VALIDATION_MAX_AUTO_SCORE`: Maximum confidence from automated scoring (default: 0.85)

### Search Configuration
- `SEARCH_MIN_TERM_LENGTH`: Minimum search term length (default: 3)
- `SEARCH_MAX_RESULTS_DEFAULT`: Default maximum search results (default: 50)
- `SEARCH_HIGHLIGHT_ENABLED`: Enable search result highlighting (default: true)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Knowledge Object Management
- `POST   /api/v1/knowledge`                 # Create knowledge object
- `GET    /api/v1/knowledge/{id}`            # Retrieve knowledge object by ID
- `GET    /api/v1/knowledge`                 # List/query knowledge objects (with filtering, pagination)
- `PUT    /api/v1/knowledge/{id}`            # Update knowledge object
- `DELETE /api/v1/knowledge/{id}`            # Soft delete knowledge object
- `POST   /api/v1/knowledge/{id}/restore`    # Restore soft-deleted knowledge object
- `GET    /api/v1/knowledge/{id}/history`    # Get version history of knowledge object

### Knowledge Validation
- `POST   /api/v1/knowledge/{id}/validate`   # Validate knowledge object status
- `POST   /api/v1/knowledge/{id}/request-review` # Request human validation
- `POST   /api/v1/knowledge/{id}/review`     # Submit human review (approve/reject/feedback)

### Knowledge Relationships
- `POST   /api/v1/knowledge/{id}/relate`     # Create relationship to another knowledge object
- `DELETE /api/v1/knowledge/{id}/relate/{relId}/{targetId}` # Delete specific relationship
- `GET    /api/v1/knowledge/{id}/related`    # Get directly related knowledge objects
- `GET    /api/v1/knowledge/{id}/related-tree` # Get related knowledge objects (transitive closure)

### Knowledge Search & Query
- `GET    /api/v1/knowledge/search`          # Full-text search knowledge objects
- `POST   /api/v1/knowledge/query`           # Complex query with filters and aggregations
- `GET    /api/v1/knowledge/tags`            # Get all used tags with counts
- `GET    /api/v1/knowledge/tag/{tag}`       # Get knowledge objects by tag

### Knowledge Lifecycle & Maintenance
- `POST   /api/v1/knowledge/decay`           # Trigger knowledge decay process
- `POST   /api/v1/knowledge/archive`         # Trigger archival of expired knowledge
- `GET    /api/v1/knowledge/stats`           # Get knowledge base statistics

## Request/Response Models

### Knowledge Object
- **Request**: `KnowledgeCreate` (type, title, description, content, tags, source)
- **Response**: `KnowledgeObject` (id, type, title, description, content, tags, confidence, validityPeriod, source, relationships, metadata, createdAt, updatedAt, version)

### Knowledge Validation Request
- **Request**: `ValidationRequest` (force: boolean, reviewerId: string (optional))
- **Response**: `ValidationResult` (isValid: boolean, confidence: float, validationMethod: enum, reviewerId: string (optional), reviewedAt: timestamp (optional), feedback: string (optional))

### Knowledge Relationship
- **Request**: `KnowledgeRelationshipCreate` (type: enum, targetId: uuid, strength: float [0.0-1.0])
- **Response**: `KnowledgeRelationship` (id, sourceId, targetId, type, strength, createdAt)

### Knowledge Search Result
- **Response**: `SearchResult` (objects: KnowledgeObject[], total: number, page: number, size: number, highlights: mapping)

### Knowledge Statistics
- **Response**: `KnowledgeStats` (totalObjects: number, byType: mapping, bySource: mapping, avgConfidence: float, objectsAddedToday: number, objectsUpdatedToday: number)

## Dependencies

- **Authentication Service**: For user validation and tenant context
- **Organization Service**: For organization/tenant context
- **PostgreSQL**: Stores knowledge object metadata, relationships, version history, and tenant information
- **MongoDB**: Stores flexible knowledge object content (JSON documents)
- **Redis**: Caching layer for frequently accessed knowledge objects and search results
- **Authentication Service**: For validating user permissions and tenant isolation
- **Event Publisher**: Publishes knowledge lifecycle events to Kafka for other services

## Event Contracts

### Events Published
- `knowledge.created.v1` - When a new knowledge object is created
- `knowledge.updated.v1` - When a knowledge object is updated
- `knowledge.validated.v1` - When a knowledge object receives validation (human or automated)
- `knowledge.deleted.v1` - When a knowledge object is soft deleted
- `knowledge.restored.v1` - When a soft deleted knowledge object is restored
- `knowledge.relationship.added.v1` - When a relationship is created between knowledge objects
- `knowledge.relationship.removed.v1` - When a relationship is removed between knowledge objects
- `knowledge.decay.processed.v1` - When the knowledge decay process runs
- `knowledge.archived.v1` - When knowledge objects are archived
- `knowledge.validation.requested.v1` - When human validation is requested
- `knowledge.validation.completed.v1` - When human validation is completed

### Events Consumed
- `insight.generated.v1` - From Insight Generation Service when new insight is created
- `pattern.discovered.v1` - From Analysis Services when new pattern is discovered
- `recommendation.made.v1` - From Recommendation Services when new recommendation is made
- `execution.results.available.v1` - From Execution Domain when test results are available
- `feedback.received.v1` - From Collaboration Domain when user feedback is received
- `external.knowledge.imported.v1` - From Integration Domain when external knowledge is imported

## Database Schema

### PostgreSQL Schema
#### knowledge_objects Table
- `id`: UUID (Primary Key)
- `tenant_id`: UUID (Foreign Key to tenants)
- `type`: ENUM (FACT, INSIGHT, PATTERN, RECOMMENDATION, METRIC, TREND)
- `title`: String
- `description`: Text
- `confidence`: Float [0.0-1.0]
- `validity_start`: Timestamp
- `validity_end`: Timestamp
- `source_type`: ENUM (SYSTEM, HUMAN, EXTERNAL_SYSTEM, ML_MODEL)
- `source_id`: String
- `metadata`: JSONB (for flexible metadata)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `version`: Integer (optimistic locking)

#### knowledge_relationships Table
- `id`: UUID (Primary Key)
- `source_object_id`: UUID (Foreign Key to knowledge_objects)
- `target_object_id`: UUID (Foreign Key to knowledge_objects)
- `relationship_type`: ENUM (RELATES_TO, DERIVED_FROM, CONTRADICTS, SUPPORTS)
- `strength`: Float [0.0-1.0]
- `created_at`: Timestamp

#### knowledge_version_history Table
- `id`: UUID (Primary Key)
- `knowledge_object_id`: UUID (Foreign Key to knowledge_objects)
- `version`: Integer
- `changed_fields`: Text (JSON array of changed field names)
- `change_reason`: Text (optional)
- `changed_by`: UUID (Foreign Key to users, optional)
- `changed_at`: Timestamp

#### knowledge_tags Table (many-to-many)
- `knowledge_object_id`: UUID (Foreign Key to knowledge_objects)
- `tag`: String (indexed)
- `created_at`: Timestamp

### MongoDB Schema
#### knowledge_contents Collection
- `_id`: ObjectID (matches knowledge_objects.id in PostgreSQL)
- `content`: JSON (flexible schema for knowledge object content)
- `updated_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (admin, editor, viewer)
- Tenant isolation ensuring users can only access knowledge objects in their tenant
- Object-level permissions for sensitive knowledge objects
- Public knowledge objects accessible to all authenticated users (configurable)

### Data Protection
- Knowledge object content stored in MongoDB with optional field-level encryption
- Sensitive metadata fields encrypted at rest
- TLS encryption for all data in transit
- Regular security scanning of stored knowledge content
- Audit logging for all knowledge object access and modifications

### Content Moderation
- Optional integration with content moderation services
- Configurable profanity and spam detection
- Quarantine flow for potentially inappropriate knowledge
- Appeal process for moderated knowledge

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Databases**: PostgreSQL (metadata/relationships) + MongoDB (content/documents)
- **Migrations**: Alembic (PostgreSQL), Mongock (MongoDB)
- **Caching**: Redis
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting, property-based testing for schemas
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
┌─► API Layer      │    │ Business Logic   │    │ Data Access      │
│  (REST Endpoints)│    │ (Knowledge CRUD, │    │ (PostgreSQL      │
│                  │    │ Validation,      │    │  + MongoDB,      │
└─────────────────┘    │  Relationships,  │    │  Search)         │
                       │  Lifecycle Mgmt) │    └──────────────────┘
                       └──────────────────┘    ┌──────────────────┐
                                                │ External Services│
                                                │ (Kafka, Auth)    │
                                                └──────────────────┘
```

## Running Tests

```bash
# From the knowledge-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_knowledge_crud.py
pytest tests/test_knowledge_validation.py
pytest tests/test_knowledge_relationships.py
pytest tests/test_knowledge_search.py
pytest tests/test_knowledge_lifecycle.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Use managed MongoDB (AWS DocumentDB, MongoDB Atlas, etc.)
- Use managed Redis (AWS ElastiCache, Redis Cloud, etc.)
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for both PostgreSQL and MongoDB
- Configure audit logging for knowledge object access (HIPAA/GDPR compliance)

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for PostgreSQL reporting queries
- MongoDB sharding for large knowledge bases
- Redis clustering for high availability
- Search optimization with proper indexing
- Batch processing for knowledge decay and archival jobs
- CDN for serving knowledge object previews/thumbnails

### Data Integrity & Consistency
- Dual-write pattern during database migrations
- Eventual consistency model between PostgreSQL and MongoDB
- Reconciliation jobs to detect and resolve inconsistencies
- Backup validation and restore testing
- Point-in-time recovery capabilities for both databases

## Maintenance

### Database Migrations
```bash
# Generate new migration after model changes (PostgreSQL)
alembic revision --autogenerate -m "description"

# Apply pending migrations (PostgreSQL)
alembic upgrade head

# Rollback last migration (PostgreSQL)
alembic downgrade -1

# MongoDB migrations handled by Mongock
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

### Knowledge Base Maintenance
- **Regular**: Monthly knowledge decay and archival jobs
- **Quarterly**: Knowledge relevance review and cleanup
- **Annual**: Knowledge taxonomy review and update
- **Continuous**: Monitoring of knowledge creation and usage patterns
- **Backup**: Daily snapshots with weekly full backups

## Product Considerations

### Knowledge Object Types Supported
- **FACT**: Verifiable information (e.g., "Test X fails on Browser Y")
- **INSIGHT**: Actionable intelligence derived from analysis (e.g., "Tests on Framework Z have 30% higher failure rate")
- **PATTERN**: Recurring structures or sequences (e.g., "Authentication failures peak every Monday at 9 AM")
- **RECOMMENDATION**: Suggested actions for improvement (e.g., "Increase test timeout for API endpoint Y")
- **METRIC**: Quantitative measurements (e.g., "Average test execution time: 4.2s")
- **TREND**: Directional changes over time (e.g., "Test failure rate decreasing 2% weekly")

### Knowledge Sources Supported
- **SYSTEM**: Automatically generated by platform services
- **HUMAN**: Manually entered by users or experts
- **EXTERNAL_SYSTEM**: Imported from external tools (Jira, TestRail, etc.)
- **ML_MODEL**: Generated by machine learning models

### Relationship Types Supported
- **RELATES_TO**: General association between knowledge objects
- **DERIVED_FROM**: One knowledge object is based on or derived from another
- **CONTRADICTS**: One knowledge object contradicts or opposes another
- **SUPPORTS**: One knowledge object provides evidence or support for another

### Validation Methods
- **AUTOMATIC**: Confidence scored by automated algorithms
- **HUMAN**: Reviewed and scored by human expert
- **HYBRID**: Combination of automated scoring and human review
- **EXTERNAL**: Validation status imported from external system

### Search Capabilities
- **Full-text search**: On title, description, and content fields
- **Field-based search**: On type, source, tags, date ranges, confidence levels
- **Tag-based search**: By single or multiple tags
- **Relationship traversal**: Find related knowledge objects through chains
- **Similarity search**: Find semantically similar knowledge (planned)
- **Geographic search**: Location-based filtering (if geographic data present)

## Future Roadmap

### Phase 1: Core Knowledge Management (Complete)
- Basic CRUD operations for knowledge objects
- Knowledge validation workflow
- Relationship management
- Basic search and querying
- Event publishing for knowledge lifecycle

### Phase 2: Enhanced Intelligence Features
- Advanced search capabilities (fuzzy, semantic)
- Knowledge graph visualization and traversal
- Automated knowledge discovery from execution data
- Collaborative knowledge editing and commenting
- Knowledge usage analytics and recommendations

### Phase 3: Advanced Integration & Federation
- External knowledge base integration (Wikipedia, domain ontologies)
- Knowledge sharing and federation between tenants
- Knowledge marketplace and trading
- Advanced ML-assisted knowledge creation and validation
- Real-time knowledge streaming and alerts