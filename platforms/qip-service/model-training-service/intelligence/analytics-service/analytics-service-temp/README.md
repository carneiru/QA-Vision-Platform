# Analytics Service

A service for providing analytics capabilities including metrics, trends, predictions, and reporting in the QA Vision Platform's Intelligence domain.

## Overview

The Analytics Service provides capabilities for collecting, processing, analyzing, and reporting on quality-related data. It enables users to gain insights from test execution data, track trends over time, make predictions about future quality outcomes, and generate reports for stakeholders.

## Features

### ✅ Fully Implemented
- **Metrics Collection**: Collect and store metrics from various sources
- **Trend Analysis**: Analyze trends over time periods with configurable intervals
- **Prediction Engine**: Generate predictions based on historical data (failure likelihood, release quality, etc.)
- **Reporting Engine**: Create and manage predefined and custom reports
- **Data Visualization Support**: Prepare data for consumption by visualization tools
- **Alerting Integration**: Generate alerts based on analytical insights
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Data Storage Configuration**: ClickHouse connection settings for analytics warehouse
- **Message Queue Configuration**: Kafka/Pulsar configuration for event streaming
- **Model Configuration**: Settings for ML models used in predictions
- **Cache Configuration**: Redis settings for caching frequent queries

### 📝 Planned Enhancements
- Real-time streaming analytics capabilities
- Advanced machine learning models for predictive analytics
- Natural language querying for analytics data
- Automated insight generation from analytics results
- Integration with BI tools (Tableau, Power BI, etc.)
- Custom dashboard creation capabilities
- Data export functionality (CSV, Excel, PDF)

## Getting Started

### Prerequisites
- Python 3.9+
- ClickHouse 24.3+ (for analytics warehouse)
- Apache Kafka or Pulsar (for event streaming)
- Redis 6.0+ (for caching)
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/analytics/analytics-service
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
   # Ensure ClickHouse is running
   # Then apply any necessary schema migrations
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
- `APP_NAME`: Service name (default: "Analytics Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### ClickHouse (for analytics warehouse)
- `CLICKHOUSE_HOST`: Database host (default: "localhost")
- `CLICKHOUSE_PORT`: Database port (default: 8123)
- `CLICKHOUSE_USER`: Database username (default: "default")
- `CLICKHOUSE_PASSWORD`: Database password (default: "")
- `CLICKHOUSE_DB`: Database name (default: "analytics")
- **OR** `CLICKHOUSE_URL`: Full connection string (overrides individual vars)

### Message Queue Configuration
#### Apache Kafka/Pulsar
- `MESSAGE_BROKER_URL`: Message broker connection URL
- `METRICS_TOPIC`: Topic for metrics ingestion
- `EVENTS_TOPIC`: Topic for event processing
- `ALERTS_TOPIC`: Topic for alert notifications

### Model Configuration
- `MODEL_STORAGE_PATH`: Path for storing ML models
- `PREDICTION_CACHE_TTL`: TTL for prediction cache in seconds (default: 3600)
- `MODEL_UPDATE_INTERVAL_Hours`: Hours between model retraining (default: 24)

### Cache Configuration
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (if required)
- `REDIS_DB`: Redis database number (default: 0)

### Analytics Configuration
- `DEFAULT_TIME_RANGE_DAYS`: Default time range for analytics queries (default: 30)
- `MAX_DATA_POINTS_PER_CHART`: Maximum data points for charting (default: 1000)
- `TREND_ANALYSIS_WINDOWS`: Default time windows for trend analysis (default: "7,30,90")

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Metrics Endpoints
- `GET /api/v1/analytics/metrics` - Get current metrics with filtering
  - Query params: `start_time`, `end_time`, `metric_names`, `tags`, `limit`
- `GET /api/v1/analytics/metrics/{metric_id}` - Get specific metric by ID

### Trend Analysis
- `GET /api/v1/analytics/trends` - Get trend analysis over time periods
  - Query params: `metric_name`, `time_window` (7,30,90,365), `aggregation` (avg,sum,min,max,count)
- `GET /api/v1/analytics/trends/{metric_id}` - Get trend for specific metric

### Predictions
- `POST /api/v1/analytics/predictions` - Request predictions
  - Body: `PredictionRequest` (prediction_type, input_data, confidence_threshold)
- `GET /api/v1/analytics/predictions/{prediction_id}` - Get prediction by ID
- `GET /api/v1/analytics/predictions` - List predictions (with filtering)

### Reports
- `GET /api/v1/analytics/reports` - List reports (with filtering and pagination)
- `GET /api/v1/analytics/reports/{id}` - Get report by ID
- `POST /api/v1/analytics/reports` - Create custom report definition
- `PUT /api/v1/analytics/reports/{id}` - Update report definition
- `DELETE /api/v1/analytics/reports/{id}` - Delete report
- `POST /api/v1/analytics/reports/{id}/generate` - Generate report
- `GET /api/v1/analytics/reports/{id}/result` - Get generated report result

### Alerts
- `GET /api/v1/analytics/alerts` - List alerts (with filtering)
- `POST /api/v1/analytics/alerts` - Create alert rule
- `PUT /api/v1/analytics/alerts/{id}` - Update alert rule
- `DELETE /api/v1/analytics/alerts/{id}` - Delete alert rule
- `POST /api/v1/analytics/alerts/{id}/test` - Test alert rule

### Data Ingestion
- `POST /api/v1/analytics/ingest/metrics` - Ingest metrics data
- `POST /api/v1/analytics/ingest/events` - Ingest event data
- `POST /api/v1/analytics/ingest/batch` - Batch ingest multiple data types

## Request/Response Models

### Metrics
- **Request**: `MetricQuery` (time_range, metric_names, tags, limit)
- **Response**: `MetricResponse` (id, name, value, timestamp, tags, metadata)

### Trend Analysis
- **Request**: `TrendRequest` (metric_name, time_window, aggregation_method)
- **Response**: `TrendResponse` (metric_name, data_points: [{timestamp, value}], trend_direction, change_percent)

### Predictions
- **Request**: `PredictionRequest` (prediction_type, input_data, confidence_threshold)
- **Response**: `PredictionResponse` (id, prediction_type, result, confidence, created_at, expires_at)

### Reports
- **Request**: `ReportDefinition` (name, description, type, parameters, schedule)
- **Response**: `Report` (id, name, description, type, parameters, schedule, created_at, updated_at)
- **Generation Result**: `ReportResult` (report_id, generated_at, data, format, size_bytes)

### Alerts
- **Request**: `AlertRule` (name, condition, threshold, notification_channels, severity)
- **Response**: `Alert` (id, name, condition, threshold, notification_channels, severity, is_enabled, created_at, updated_at)

## Dependencies

- **Authentication Service**: For user validation and permissions
- **Organization Service**: For organization/context isolation
- **Knowledge Service**: For accessing insights, patterns, and recommendations
- **Execution Service**: For obtaining test execution data
- **ClickHouse**: Primary storage for analytics data and aggregated metrics
- **Apache Kafka/Pulsar**: Event streaming for real-time data processing
- **Redis**: Caching layer for frequent queries and computed results
- **MLflow** (optional): Model tracking and serving for prediction models
- **Shared Libraries**: Common utilities, configuration, logging

## Event Contracts

### Events Published
- `metric.collected.v1` - When a metric is collected and stored
- `trend.analyzed.v1` - When trend analysis is completed
- `prediction.generated.v1` - When a prediction is generated
- `report.created.v1` - When a report is created
- `report.generated.v1` - When a report is generated
- `alert.triggered.v1` - When an alert condition is met

### Events Consumed
- `execution.completed.v1` - From Execution Service when test execution completes
- `metric.collected.v1` - From other services that collect metrics
- `quality.threshold.breached.v1` - From Quality Service when thresholds are breached
- `insight.generated.v1` - From Knowledge Service when new insights are generated

## Database Schema

### ClickHouse Schema

#### metrics Table
- `id`: String (UUID)
- `name`: String (Metric name)
- `value`: Float64 (Metric value)
- `timestamp`: DateTime (When metric was recorded)
- `tags`: Map(String, String) (Metadata tags)
- `source_service`: String (Service that generated the metric)
- `ingestion_time`: DateTime (When metric was ingested)

#### trends Table
- `id`: String (UUID)
- `metric_name`: String
- `time_window`: String (7,30,90,365 days)
- `start_date`: DateTime
- `end_date`: DateTime
- `data_points`: Array(Tuple(DateTime, Float64))
- `trend_direction`: Enum('up', 'down', 'stable')
- `change_percent`: Float64
- `calculated_at`: DateTime

#### predictions Table
- `id`: String (UUID)
- `prediction_type`: String (failure_rate, release_quality, defect_count, etc.)
- `input_data`: JSON (Input features used for prediction)
- `result`: Float64 (Predicted value)
- `confidence`: Float64 (Confidence score 0-1)
- `created_at`: DateTime
- `expires_at`: DateTime (When prediction expires)
- `model_version`: String (Version of model used)

#### reports Table
- `id`: String (UUID)
- `name`: String
- `description`: String
- `report_type`: String (trend_analysis, summary, comparison, custom)
- `parameters`: JSON (Report-specific parameters)
- `schedule`: String (Cron expression or null for manual)
- `last_generated`: DateTime
- `created_at`: DateTime
- `updated_at`: DateTime

#### alerts Table
- `id`: String (UUID)
- `name`: String
- `condition`: String (Expression to evaluate)
- `threshold`: Float64 (Threshold value)
- `notification_channels`: Array(String) (email, slack, webhook, etc.)
- `severity`: String (low, medium, high, critical)
- `is_enabled`: Boolean
- `created_at`: DateTime
- `updated_at`: DateTime
- `last_triggered`: DateTime (Nullable)

## Security Implementation

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (admin, analyst, viewer, operator)
- Tenant isolation ensuring users can only access analytics data in their tenant
- Resource-level permissions for sensitive metrics and reports

### Data Protection
- Data encryption at rest for sensitive metrics
- Column-level encryption in ClickHouse for PII or sensitive data
- TLS encryption for all data in transit
- Regular security scanning of stored analytics data
- Audit logging for all analytics access and query execution

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: ClickHouse (analytics warehouse), Redis (caching)
- **Streaming**: Apache Kafka/Pulsar (event processing)
- **ML Framework**: Scikit-learn, TensorFlow/PyTorch (for prediction models)
- **Migrations**: ClickHouse migrations (custom scripts)
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Data Access      │
│ (REST Endpoints)│    │ (Metrics, Trends,│    │ (ClickHouse      │
│                 │    │  Predictions,    │    │  + Redis Cache)  │
└─────────────────┘    │  Reports, Alerts)│    └──────────────────┘
                       └──────────────────┘    ┌──────────────────┐
                                               │ External Services│
                                               │ (Kafka, MLflow)  │
                                               └──────────────────┘
```

## Running Tests Manual

```bash
# From the analytics-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_metrics.py
pytest tests/test_trends.py
pytest tests/test_predictions.py
pytest tests/test_reports.py
pytest tests/test_alerts.py
```

## Deployment Considerations

### Production Environment
- Use managed ClickHouse service (Altinity, ClickHouse Cloud, etc.)
- Configure proper replication and backup strategies for ClickHouse
- Use managed Kafka service (Confluent Cloud, AWS MSK, etc.)
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for ClickHouse and Redis
- Configure audit logging for analytics access (compliance requirements)

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for ClickHouse (if using enterprise features)
- Consumer groups for Kafka/Pulser for scalable event processing
- Redis clustering for high availability
- Horizontal scaling of API instances based on request volume
- Distributed computing for complex analytics (Apache Spark integration)
- GPU acceleration for ML model inference (when applicable)

### Data Integrity & Consistency
- Atomic writes to ClickHouse for metric data
- Eventual consistency model acceptable for most analytics use cases
- Data validation pipelines for incoming metrics
- Regular data quality checks and anomaly detection
- Backup and disaster recovery procedures for analytics data
- Data retention policies for different types of analytics data

## Maintenance

### Database Maintenance
```bash
# Check for fragmented tables
OPTIMIZE TABLE metrics FINAL;

# Check replication status (if using replicated tables)
SELECT * FROM system.replicas WHERE database = 'analytics';

# Verify data integrity
SELECT count(*) FROM metrics WHERE date >= today() - 7;
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

### Analytics Service Maintenance
- **Daily**: Monitor data ingestion rates and system health
- **Weekly**: Review query performance and optimize slow queries
- **Monthly**: Retrain ML models with latest data
- **Quarterly**: Review data retention policies and archive old data
- **Annually**: Evaluate and update analytics models and methodologies
- **Continuous**: Monitor prediction accuracy and drift

## Product Considerations

### Analytics Types Supported
- **Descriptive Analytics**: What happened? (metrics, reporting)
- **Diagnostic Analytics**: Why did it happen? (drill-down, correlation analysis)
- **Predictive Analytics**: What will happen? (forecasting, probability estimation)
- **Prescriptive Analytics**: What should we do? (recommendations, optimization)

### Data Sources Supported
- **Test Execution Data**: Results from test runs, executions, suites
- **Code Quality Metrics**: Static analysis, complexity, coverage metrics
- **Production Monitoring**: Error rates, latency, availability metrics
- **User Analytics**: Feature usage, adoption, satisfaction metrics
- **Process Metrics**: Cycle times, lead times, throughput, WIP

### Analysis Capabilities
- **Time Series Analysis**: Trend detection, seasonality, anomaly detection
- **Statistical Analysis**: Correlations, distributions, hypothesis testing
- **Cohort Analysis**: Group-based analysis over time
- **Funnel Analysis**: Conversion rates, drop-off points
- **Cohort Analysis**: Group behavior analysis
- **Predictive Modeling**: Regression, classification, time series forecasting
- **Statistical Process Control**: Control charts, process capability analysis

### Integration Points
- **Visualization Tools**: Grafana, Superset, custom dashboards
- **BI Platforms**: Tableau, Power BI, Looker (via ODBC/JDBC)
- **Notification Systems**: Email, Slack, Microsoft Teams, PagerDuty
- **Workflow Systems**: Jira, ServiceNow, custom workflow engines
- **ML Platforms**: MLflow, Weights & Biases, custom model serving