# Observability Collector and Storage Service

A service for collecting, processing, and storing observability data (logs, metrics, traces, and profiles) in the QA Vision Platform's Intelligence domain.

## Overview

The Observability Collector and Storage Service provides comprehensive observability capabilities by collecting, processing, and storing telemetry data from all services in the QEOS platform. It implements the four pillars of observability: logs, metrics, traces, and profiles, enabling deep system observability for monitoring, debugging, and performance analysis.

## Features

### ✅ Fully Implemented

- **Log Collection**: Collect and store structured logs from all services
- **Metrics Collection**: Gather and store system and business metrics
- **Trace Collection**: Capture and store distributed traces for request tracing
- **Profile Collection**: Collect and store profiling data for performance analysis
- **Data Processing**: Normalize, enrich, and tag observability data
- **Storage Management**: Efficient storage with retention policies and tiered storage
- **Query Interface**: Provide APIs for querying observability data
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required

- **Storage Configuration**: Settings for log (Loki), metric (Prometheus), trace (Tempo), and profile (Pyroscope) storage
- **Database Configuration**: PostgreSQL connection settings for metadata and configuration
- **Message Queue Configuration**: Kafka/Pulsar configuration for event streaming
- **Retention Policies**: Data retention rules for different data types
- **Processing Configuration**: Batch sizes, processing intervals, resource limits
- **Alerting Configuration**: Integration with alerting systems

### 📝 Planned Enhancements

- Real-time stream processing capabilities
- Advanced data compression and encoding schemes
- Machine learning-based anomaly detection on observability data
- Cross-service correlation and dependency mapping
- Custom dashboard creation capabilities
- Data export functionality (various formats)
- Integration with external observability platforms

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 12+ (for metadata storage)
- Loki 2.5+ (for log storage)
- Prometheus 2.30+ (for metrics storage)
- Tempo 2.0+ (for trace storage)
- Pyroscope 0.15+ (for profile storage)
- Apache Kafka or Pulsar (for event streaming)
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/observability/observability-service
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
- `APP_NAME`: Service name (default: "Observability Collector and Storage Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for metadata)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "observability")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Storage Configuration
#### Loki (Logs)
- `LOKI_URL`: Loki server URL (default: "http://localhost:3100")
- `LOKI_USERNAME`: Loki username (optional)
- `LOKI_PASSWORD`: Loki password (optional)

#### Prometheus (Metrics)
- `PROMETHEUS_URL`: Prometheus server URL (default: "http://localhost:9090")
- `PROMETHEUS_USERNAME`: Prometheus username (optional)
- `PROMETHEUS_PASSWORD`: Prometheus password (optional)

#### Tempo (Traces)
- `TEMPO_URL`: Tempo server URL (default: "http://localhost:3200")
- `TEMPO_USERNAME`: Tempo username (optional)
- `TEMPO_PASSWORD`: Tempo password (optional)

#### Pyroscope (Profiles)
- `PYROSCOPE_URL`: Pyroscope server URL (default: "http://localhost:4040")
- `PYROSCOPE_USERNAME`: Pyroscope username (optional)
- `PYROSCOPE_PASSWORD`: Pyroscope password (optional)

### Message Queue Configuration
#### Apache Kafka/Pulsar
- `MESSAGE_BROKER_URL`: Message broker connection URL
- `OBSERVABILITY_LOGS_TOPIC`: Topic for log data
- `OBSERVABILITY_METRICS_TOPIC`: Topic for metric data
- `OBSERVABILITY_TRACES_TOPIC`: Topic for trace data
- `OBSERVABILITY_PROFILES_TOPIC`: Topic for profile data
- `PROCESSED_OBSERVABILITY_TOPIC`: Topic for processed observability events

### Processing Configuration
- `BATCH_SIZE`: Number of records to process in each batch (default: 1000)
- `PROCESSING_INTERVAL_SECONDS`: Seconds between processing cycles (default: 30)
- `MAX_CONCURRENT_JOBS`: Maximum concurrent processing jobs (default: 5)
- `LOG_RETENTION_DAYS`: Log retention period in days (default: 30)
- `METRIC_RETENTION_DAYS`: Metrics retention period in days (default: 90)
- `TRACE_RETENTION_DAYS`: Trace retention period in days (default: 14)
- `PROFILE_RETENTION_DAYS`: Profile retention period in days (default: 30)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Log Management
- `POST /api/v1/logs/collect` - Collect and store log entries
  - Body: `LogCollectionRequest` (service, level, message, timestamp, tags, tenant_id)
- `GET /api/v1/logs/query` - Query log entries
  - Query params: `query`, `start_time`, `end_time`, `limit`, `offset`, `service`, `level`
- `GET /api/v1/logs/{log_id}` - Get specific log entry
  - Path param: `log_id` (log UUID)

### Metrics Management
- `POST /api/v1/metrics/collect` - Collect and store metric data points
  - Body: `MetricsCollectionRequest` (metric_name, value, timestamp, labels, tenant_id)
- `GET /api/v1/metrics/query` - Query metric data
  - Query params: `metric_name`, `start_time`, `end_time`, `step`, `labels`
- `GET /api/v1/metrics/{metric_id}` - Get specific metric metadata
  - Path param: `metric_id` (metric UUID)

### Trace Management
- `POST /api/v1/traces/collect` - Collect and store trace data
  - Body: `TraceCollectionRequest` (trace_id, spans, timestamp, tenant_id)
- `GET /api/v1/traces/query` - Query trace data
  - Query params: `trace_id`, `start_time`, `end_time`, `service`, `operation`, `limit`
- `GET /api/v1/traces/{trace_id}` - Get specific trace
  - Path param: `trace_id` (trace UUID)

### Profile Management
- `POST /api/v1/profiles/collect` - Collect and store profile data
  - Body: `ProfileCollectionRequest` (profile_type, data, timestamp, tenant_id)
- `GET /api/v1/profiles/query` - Query profile data
  - Query params: `profile_type`, `start_time`, `end_time`, `limit`, `offset`
- `GET /api/v1/profiles/{profile_id}` - Get specific profile
  - Path param: `profile_id` (profile UUID)

### Data Management
- `DELETE /api/v1/data/expire` - Manually trigger data expiration based on retention policies
  - Body: `DataExpirationRequest` (data_types, force_expiration)
- `GET /api/v1/storage/stats` - Get storage statistics for all data types
- `POST /api/v1/storage/maintenance` - Trigger storage maintenance operations

## Request/Response Models

### Log Collection
- **Request**: `LogCollectionRequest` (service: str, level: str, message: str, timestamp: datetime, tags: Dict[str, str], tenant_id: UUID)
- **Response**: `LogResponse` (id: UUID, service: str, level: str, message: str, timestamp: datetime, stored_at: datetime)

### Metrics Collection
- **Request**: `MetricsCollectionRequest` (metric_name: str, value: float, timestamp: datetime, labels: Dict[str, str], tenant_id: UUID)
- **Response**: `MetricResponse` (id: UUID, metric_name: str, value: float, timestamp: datetime, stored_at: datetime)

### Trace Collection
- **Request**: `TraceCollectionRequest` (trace_id: UUID, spans: List[Span], timestamp: datetime, tenant_id: UUID)
- **Response**: `TraceResponse` (trace_id: UUID, span_count: int, stored_at: datetime)

### Profile Collection
- **Request**: `ProfileCollectionRequest` (profile_type: str, data: bytes, timestamp: datetime, tenant_id: UUID)
- **Response**: `ProfileResponse` (id: UUID, profile_type: str, size_bytes: int, stored_at: datetime)

### Data Expiration
- **Request**: `DataExpirationRequest` (data_types: List[str], force_expiration: bool)
- **Response**: `DataExpirationResponse` (expired_logs: int, expired_metrics: int, expired_traces: int, expired_profiles: int, processing_time_ms: int)

### Storage Stats
- **Response**: `StorageStatsResponse` (logs: StorageStats, metrics: StorageStats, traces: StorageStats, profiles: StorageStats)

## Dependencies

- **Authentication Service**: For user validation and permissions
- **Organization Service**: For organization/context isolation
- **Execution Service**: For obtaining telemetry data from test executions
- **PostgreSQL**: Stores metadata, configuration, and processing state
- **Loki**: Stores structured log data
- **Prometheus**: Stores metrics data
- **Tempo**: Stores distributed trace data
- **Pyroscope**: Stores profiling data
- **Apache Kafka/Pulsar**: Event streaming for real-time data processing
- **Redis**: Caching layer for frequent queries and temporary storage
- **Shared Libraries**: Common utilities, configuration, logging

## Event Contracts

### Events Published
- `observability.logs.collected.v1` - When log data is collected and stored
- `observability.metrics.collected.v1` - When metric data is collected and stored
- `observability.traces.collected.v1` - When trace data is collected and stored
- `observability.profiles.collected.v1` - When profile data is collected and stored
- `observability.data.expired.v1` - When data is removed due to retention policies
- `observatory.alert.triggered.v1` - When observability data triggers an alert condition

### Events Consumed
- `application.logs.v1` - From all services when log entries are generated
- `application.metrics.v1` - From all services when metrics are recorded
- `application.traces.v1` - From all services when traces are generated
- `application.profiles.v1` - From all services when profiles are captured
- `alert.triggered.v1` - From Alerting Service when alerts are triggered (for correlation)
- `deployment.completed.v1` - From Deployment Service when releases are deployed

## Database Schema

### PostgreSQL Schema

#### observability_config Table
- `id`: UUID (Primary Key)
- `config_key`: String (Configuration key)
- `config_value`: JSONB (Configuration value)
- `description`: Text (Description of what this config controls)
- `updated_at`: Timestamp
- `updated_by`: UUID (Foreign Key to users table)

#### collection_jobs Table
- `id`: UUID (Primary Key)
- `job_type`: String (log, metric, trace, profile)
- `status`: String (pending, processing, completed, failed)
- `started_at`: Timestamp
- `completed_at`: Timestamp (Nullable)
- `processed_count`: Integer
- `failed_count`: Integer
- `error_message`: Text (Nullable)
- `created_at`: Timestamp
- `created_by`: UUID (Foreign Key to users table)

#### data_retention_policies Table
- `id`: UUID (Primary Key)
- `data_type`: String (log, metric, trace, profile)
- `retention_days`: Integer
- `hot_storage_days`: Integer (Nullable)
- `warm_storage_days`: Integer (Nullable)
- `cold_storage_days`: Integer (Nullable)
- `created_at`: Timestamp
- `updated_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- JWT-based authentication with refresh token rotation
- Role-based access control (admin, operator, analyst, viewer)
- Tenant isolation ensuring users can only access observability data from their tenant
- Data-level permissions for sensitive observability data (security-related traces/logs)
- Service-to-service authentication for internal communications

### Data Protection
- Observability metadata stored in PostgreSQL with standard security practices
- Log data stored in Loki with appropriate access controls
- Metrics data stored in Prometheus with appropriate access controls
- Trace data stored in Tempo with appropriate access controls
- Profile data stored in Pyroscope with appropriate access controls
- TLS encryption for all data in transit
- Regular security scanning of stored observability data
- Audit logging for all observability data access, collection, and deletion
- Data anonymization capabilities for sensitive information

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Storage Backends**: Loki (logs), Prometheus (metrics), Tempo (traces), Pyroscope (profiles)
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Storage Abstraction│
│ (REST Endpoints)│    │ (Collection,     │    │ Layer              │
│                 │    │  Processing,     │    │ (Loki, Prometheus, │
└─────────────────┘    │  Retention)      │    │  Tempo, Pyroscope) │
                       └──────────────────┘    └──────────────────┘
                                ▲                   ▲
                                │                   │
                   ┌──────────────────┐    ┌──────────────────┐
                   │ External Services│    │ Internal Events  │
                   │ (Kafka, Pulsar)  │    │ (Kafka/Pulsar)   │
                   └──────────────────┘    └──────────────────┘
```

### Core Components Implementation

1. **Data Collection Agents**: Services that receive observability data from various sources
2. **Processing Engine**: Handles data normalization, enrichment, and routing
3. **Storage Abstraction Layer**: Unified interface for different storage backends
4. **Retention Management**: Enforces data retention policies across storage systems
5. **Query Service**: Provides querying capabilities across all observability data types
6. **Event Processing Service**: Consumes and produces domain events for integration
7. **Health Monitoring**: Monitors the health of all integrated storage systems

#### Data Collection Flow
1. Services emit observability data (logs, metrics, traces, profiles) via configured channels
2. Observability Collector receives the data through API endpoints or message queues
3. Data is validated, enriched with tenant/context information, and queued for processing
4. Processing workers consume the queue and route data to appropriate storage backends
5. Storage backends persist the data with appropriate indexing and tagging
6. Completion events are published for monitoring and downstream consumption
7. Retention policies are periodically enforced to remove aged data

#### Query Flow
1. User submits query via API endpoint
2. Query service parses and validates the request
3. Query is routed to appropriate storage backends based on data type
4. Results are retrieved from each backend and aggregated
5. Results are formatted and returned to the user

## Running Tests

```bash
# From the observability-collector-storage directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest/tests/test_log_collection.py
pytest/tests/test_metrics_collection.py
pytest/tests/test_trace_collection.py
pytest/tests/test_profile_collection.py
pytest/tests/test_data_retention.py
pytest/tests/test_query_service.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.) with read replicas
- Use managed logging (Grafana Cloud Loki, etc.) or clustered Loki deployment
- Use managed metrics (Prometheus-based services like Cortex, Thanos) or clustered Prometheus
- Use managed tracing (Tempo-based services) or clustered Tempo deployment
- Use managed profiling (Pyroscope-based services) or clustered Pyroscope deployment
- Use managed Kafka service (Confluent Cloud, AWS MSK, etc.)
- Configure proper connection pooling and database sizing
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for PostgreSQL
- Configure audit logging for observability data access (compliance requirements)

### Scaling Considerations
- Stateless API servers behind load balancer
- Horizontal scaling of processing workers based on queue depth
- Scalable storage backends (Loki, Prometheus, Tempo, Pyroscope all support clustering)
- Consumer groups for Kafka/Pulsar for scalable event processing
- Redis clustering for high availability
- Horizontal scaling of API instances based on request volume
- Resource allocation based on data volume profiles (logs typically require most resources)

### Data Integrity & Consistency
- ACID transactions for metadata operations in PostgreSQL
- Eventual consistency model acceptable for observability data (consistency vs. availability tradeoff)
- Data validation pipelines for incoming observability data
- Regular data quality checks and anomaly detection in input data
- Backup and disaster recovery procedures for metadata
- Data retention policies automatically enforced to manage storage growth
- Duplicate detection and handling for resubmitted data

## Maintenance

### Database Maintenance
```bash
# Vacuum and analyze tables periodically
VACUUM ANALYZE observability_config;
VACUUM ANALYZE collection_jobs;
VACUUM ANALYZE data_retention_policies;

# Check for failed jobs that need attention
SELECT * FROM collection_jobs WHERE status = 'failed' AND created_at > NOW() - INTERVAL '24 hours';

# Update index statistics
REINDEX TABLE observability_config;
REINDEX TABLE collection_jobs;
REINDEX TABLE data_retention_policies;
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

### Observability Collector and Storage Service Maintenance
- **Continuous**: Monitor data ingestion rates and system lag
- **Hourly**: Review processing job success/failure rates
- **Daily**: Verify storage systems are functioning correctly
- **Weekly**: Review storage utilization and growth trends
- **Monthly**: Test recovery procedures and backup integrity
- **Quarterly**: Review and update retention policies based on compliance requirements
- **Annually**: Evaluate storage architecture and plan for capacity upgrades
- **Continuous**: Monitor for data gaps or collection failures
- **Continuous**: Track query performance and optimize as needed

## Product Considerations

### Data Types Supported
- **Logs**: Structured log entries with standardized fields (timestamp, level, message, service, trace_id, span_id, tenant_id, etc.)
- **Metrics**: Time-series data points with labels (counter, gauge, histogram, summary types)
- **Traces**: Distributed trace data with spans representing units of work
- **Profiles**: Performance profiling data (CPU, memory, blocking, goroutine stacks)

### Collection Methods
- **Push Model**: Services actively send data to the observability collector
- **Pull Model**: Observability collector scrapes data from endpoints (primarily for metrics)
- **Agent Model**: Lightweight agents run on hosts to collect and forward data
- **Message Queue**: Data published to topics for asynchronous processing

### Integration Points
- **Service Instrumentation**: Libraries/SDKs for automatic telemetry collection in services
- **Infrastructure Monitoring**: Integration with system-level monitoring tools
- **Application Performance Monitoring (APM)**: Correlation with APM tools
- **Log Aggregation**: Integration with existing log aggregation systems
- **Metric Visualization**: Integration with Grafana and other visualization tools
- **Alerting Systems**: Integration with Alertmanager, PagerDuty, etc.

### Data Retention and Tiering
- **Hot Storage**: Recent data for immediate querying (highest performance)
- **Warm Storage**: Older data for infrequent querying (moderate cost)
- **Cold Storage**: Archived data for compliance/long-term retention (lowest cost)
- **Configurable Policies**: Different retention periods per data type and tenant
- **Automatic Tiering**: Automatic movement of data between storage tiers based on age