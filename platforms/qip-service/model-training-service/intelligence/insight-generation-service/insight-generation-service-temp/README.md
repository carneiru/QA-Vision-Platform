# Insight Generation Service

A service for generating actionable insights from quality data using machine learning and statistical analysis in the QA Vision Platform's Intelligence domain.

## Overview

The Insight Generation Service automatically analyzes quality metrics, test results, and other operational data to identify meaningful patterns, anomalies, trends, and correlations. It leverages machine learning algorithms and statistical techniques to transform raw data into actionable insights that help teams improve software quality and testing efficiency.

## Features

### ✅ Fully Implemented
- **Insight Generation Pipeline**: Automated pipeline for generating insights from multiple data sources
- **Multiple Insight Types**: Anomaly detection, trend analysis, correlation discovery, predictive insights, root cause analysis, optimization recommendations
- **Insight Management**: Create, retrieve, list, and manage insights with feedback mechanisms
- **Trending Insights**: Identify and surface currently relevant insights
- **Feedback Collection**: Collect user feedback on insight usefulness for continuous improvement
- **Manual Expiration**: Ability to manually expire insights when no longer relevant
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Data Sources Configuration**: Kafka/Pulsar topics for consuming various data streams
- **Model Configuration**: Settings for ML models used in insight generation
- **Processing Configuration**: Batch sizes, processing intervals, resource limits
- **Storage Configuration**: Database connection settings for insight persistence

### 📝 Planned Enhancements
- Real-time insight generation from streaming data
- Advanced ensemble methods for improved accuracy
- Natural language generation for insight explanations
- Collaborative insight refinement and annotation
- Integration with external knowledge bases for enrichment
- A/B testing framework for insight validation

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+ (for insight metadata storage)
- Apache Kafka or Pulsar (for event streaming)
- Redis 6.0+ (for caching and pub/sub)
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/intelligence/insight-generation/insight-generation-service
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
- `APP_NAME`: Service name (default: "Insight Generation Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for insight metadata)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "insight_gen")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Message Queue Configuration
#### Apache Kafka/Pulsar
- `MESSAGE_BROKER_URL`: Message broker connection URL
- `METRICS_TOPIC`: Topic for consuming metrics data
- `EVENTS_TOPIC`: Topic for consuming event data
- `TEST_RESULTS_TOPIC`: Topic for consuming test results
- `INSIGHTS_TOPIC`: Topic for publishing generated insights
- `FEEDBACK_TOPIC`: Topic for consuming user feedback on insights

### Model Configuration
- `MODEL_STORAGE_PATH`: Path for storing ML models
- `PREDICTION_MODEL_UPDATE_HOURS`: Hours between model retraining (default: 24)
- `ANOMALY_DETECTION_SENSITIVITY`: Sensitivity threshold for anomaly detection (default: 0.95)
- `TREND_DETECTION_MIN_POINTS`: Minimum data points for trend detection (default: 10)

### Processing Configuration
- `BATCH_SIZE`: Number of records to process in each batch (default: 1000)
- `PROCESSING_INTERVAL_SECONDS`: Seconds between processing cycles (default: 300)
- `MAX_CONCURRENT_JOBS`: Maximum concurrent insight generation jobs (default: 5)
- `INSIGHT_TTL_DAYS`: Default time-to-live for insights in days (default: 30)

### Cache Configuration
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (if required)
- `REDIS_DB`: Redis database number (default: 0)

### Insight Generation Configuration
- `MIN_CONFIDENCE_THRESHOLD`: Minimum confidence score for insight publication (default: 0.7)
- `FEEDBACK_WEIGHT_FACTOR`: Weight given to user feedback in insight scoring (default: 0.3)
- `TREND_ANALYSIS_WINDOWS`: Time windows for trend analysis in days (default: "7,30,90")
- `CORRELATION_THRESHOLD`: Minimum correlation coefficient for reporting (default: 0.6)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Insight Generation
- `POST /api/v1/insights/generate` - Generate insight from context/data
  - Body: `InsightGenerationRequest` (data_sources, insight_types, parameters)
  
### Insight Management
- `GET /api/v1/insights/{id}` - Retrieve specific insight by ID
- `GET /api/v1/insights` - List/filter insights with pagination and filtering
  - Query params: `insight_type`, `start_time`, `end_time`, `min_confidence`, `tags`, `limit`, `offset`
- `POST /api/v1/insights/{id}/feedback` - Provide feedback on insight helpfulness
  - Body: `InsightFeedback` (helpful: boolean, feedback_text: optional string)
- `GET /api/v1/insights/trending` - Get currently trending insights
  - Query params: `limit`, `time_window_hours`
- `POST /api/v1/insights/{id}/expire` - Manually expire insight early
  - Body: `InsightExpiration` (reason: optional string)

### Insight Types & Configuration
- `GET /api/v1/insights/types` - Get available insight types and their descriptions
- `GET /api/v1/insights/config` - Get current insight generation configuration
- `PUT /api/v1/insights/config` - Update insight generation configuration

## Request/Response Models

### Insight Generation Request
- **Request**: `InsightGenerationRequest` (data_sources: List[str], insight_types: Optional[List[str]], parameters: Optional[Dict[str, Any]])
- **Response**: `InsightGenerationResponse` (insight_id: str, status: str, message: str)

### Insight
- **Request/Response**: `Insight` (id, insight_type, title, description, confidence_score, supporting_data, generated_at, expires_at, tags, source_systems, metadata)

### Insight Feedback
- **Request**: `InsightFeedback` (helpful: bool, feedback_text: Optional[str])
- **Response**: `InsightFeedbackResponse` (id, insight_id, helpful, feedback_text, submitted_at, submitted_by)

### Trending Insights
- **Response**: `TrendingInsightsResponse` (insights: List[Insight], generated_at: datetime, time_window_hours: int)

### Insight Expiration
- **Request**: `InsightExpiration` (reason: Optional[str])
- **Response**: `InsightExpirationResponse` (insight_id: str, expired_at: datetime, reason: Optional[str])

### Insight Types
- **Response**: `InsightTypesResponse` (insight_types: List[InsightTypeInfo])
- **InsightTypeInfo**: (type_id: str, name: str, description: str, required_data_sources: List[str])

## Dependencies

- **Authentication Service**: For user validation and permissions
- **Organization Service**: For organization/context isolation
- **Knowledge Service**: For storing insights as knowledge objects and retrieving related knowledge
- **Execution Service**: For accessing test execution data and metrics
- **Analytics Service**: For leveraging pre-computed metrics and trends
- **PostgreSQL**: Stores insight metadata, feedback, and configuration
- **Apache Kafka/Pulsar**: Event streaming for real-time data processing and insight distribution
- **Redis**: Caching layer for frequent computations and pub/sub notifications
- **ML Libraries**: Scikit-learn, TensorFlow/PyTorch, Statsmodels (for various ML algorithms)
- **Shared Libraries**: Common utilities, configuration, logging

## Event Contracts

### Events Published
- `insight.generated.v1` - When a new insight is generated
- `insight.feedback.received.v1` - When user feedback is received on an insight
- `insight.expired.v1` - When an insight expires (naturally or manually)
- `insight.trending.updated.v1` - When trending insights are updated

### Events Consumed
- `metric.collected.v1` - From Analytics/Execution Services when metrics are collected
- `test.execution.completed.v1` - From Execution Service when test execution completes
- `quality.threshold.breached.v1` - From Quality Service when quality thresholds are breached
- `execution.results.available.v1` - From Execution Domain when test results are available
- `code.quality.updated.v1` - From Development Integration when code quality metrics are updated

## Database Schema

### PostgreSQL Schema

#### insights Table
- `id`: UUID (Primary Key)
- `insight_type`: String (Type of insight: anomaly, trend, correlation, prediction, root_cause, optimization)
- `title`: String (Brief, descriptive title)
- `description`: Text (Detailed explanation of the insight)
- `confidence_score`: Float (Confidence level 0.0-1.0)
- `supporting_data`: JSONB (Data supporting the insight, varies by insight type)
- `generated_at`: Timestamp (When insight was generated)
- `expires_at`: Timestamp (When insight expires, nullable)
- `tags`: JSONB (Array of string tags for categorization)
- `source_systems`: JSONB (Array of source system identifiers)
- `metadata`: JSONB (Additional metadata)
- `created_at`: Timestamp
- `updated_at`: Timestamp

#### insight_feedback Table
- `id`: UUID (Primary Key)
- `insight_id`: UUID (Foreign Key to insights)
- `helpful`: Boolean (Whether user found the insight helpful)
- `feedback_text`: Text (Optional user comments)
- `submitted_at`: Timestamp
- `submitted_by`: UUID (Foreign Key to users table via auth service)

#### insight_generation_config Table
- `id`: UUID (Primary Key)
- `config_key`: String (Configuration key)
- `config_value`: JSONB (Configuration value)
- `description`: Text (Description of what this config controls)
- `updated_at`: Timestamp
- `updated_by`: UUID (Foreign Key to users table)

## Security Implementation

### Authentication & Authorization
- JWT-based authentication with refresh token rotation
- Role-based access control (admin, data_scientist, analyst, viewer)
- Tenant isolation ensuring users can only access insights from their tenant
- Insight-level permissions for sensitive insights (e.g., security-related findings)

### Data Protection
- Insight content stored in PostgreSQL with standard security practices
- Supporting data stored as JSONB with appropriate access controls
- TLS encryption for all data in transit
- Regular security scanning of stored insight data
- Audit logging for all insight access, generation, and feedback submission

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Streaming**: Apache Kafka/Pulsar (event processing)
- **ML Framework**: Scikit-learn, TensorFlow/PyTorch, Statsmodels
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Data Access      │
│ (REST Endpoints)│    │ (Insight Gen,    │    │ (PostgreSQL      │
│                 │    │  Feedback,       │    │  + Cache)        │
└─────────────────┘    │  Trending, Exp)  │    └──────────────────┘
                       └──────────────────┘    ┌──────────────────┐
                                               │ External Services│
                                               │ (Kafka, MLflow)  │
                                               └──────────────────┘
```

### Insight Generation Pipeline Implementation
1. **Data Collection**: Consumes from multiple Kafka topics (metrics, events, test results)
2. **Preprocessing**: Data cleaning, normalization, feature engineering
3. **Model Application**: Applies appropriate ML models based on insight type:
   - Anomaly Detection: Isolation Forest, One-Class SVM, LSTM Autoencoders
   - Trend Analysis: Prophet, ARIMA, Linear Regression with change point detection
   - Correlation Discovery: Pearson/Spearman correlation, Mutual Information
   - Predictive Insights: XGBoost, Random Forest, LSTM for time series forecasting
   - Root Cause Analysis: PCA, Decision Trees, SHAP values for feature importance
   - Optimization Recommendations: Multi-armed bandit, Bayesian optimization
4. **Significance Testing**: Statistical validation (p-values, confidence intervals)
5. **Insight Formatting**: Structures findings into standardized insight objects
6. **Confidence Scoring**: Combines statistical significance, data quality, and model confidence
7. **Publication**: Emits insight generated events and updates knowledge base

## Running Tests

```bash
# From the insight-generation-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest/tests/test_insight_generation.py
pytest/tests/test_insight_management.py
pytest/tests/test_feedback_system.py
pytest/tests/test_trending_insights.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Configure proper connection pooling and read replicas
- Use managed Kafka service (Confluent Cloud, AWS MSK, etc.)
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for database credentials and API keys
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for PostgreSQL
- Configure audit logging for insight access (compliance requirements)

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for PostgreSQL reporting queries
- Consumer groups for Kafka/Pulsar for scalable event processing
- Redis clustering for high availability
- Horizontal scaling of API instances based on request volume
- GPU acceleration for ML model inference (when applicable)
- Distributed computing for large-scale data processing (Apache Spark integration)
- Model serving optimization (TensorFlow Serving, TorchServe)

### Data Integrity & Consistency
- ACID transactions for insight metadata operations
- Eventual consistency model acceptable for insight generation pipeline
- Data validation pipelines for incoming data streams
- Regular data quality checks and anomaly detection in input data
- Backup and disaster recovery procedures for insight metadata
- Data retention policies for different types of insights

## Maintenance

### Database Maintenance
```bash
# Vacuum and analyze tables periodically
VACUUM ANALYZE insights;
VACUUM ANALYZE insight_feedback;

# Check for insights that need cleanup
DELETE FROM insights WHERE expires_at < NOW() AND expires_at IS NOT NULL;

# Update index statistics
REINDEX TABLE insights;
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

### Insight Generation Service Maintenance
- **Hourly**: Monitor insight generation pipeline health and throughput
- **Daily**: Review generated insights for quality and relevance
- **Weekly**: Retrain ML models with latest data
- **Monthly**: Review feedback analytics and adjust insight algorithms
- **Quarterly**: Evaluate and update insight generation models and approaches
- **Annually**: Assess business impact and refine insight generation strategy
- **Continuous**: Monitor prediction accuracy, drift, and feedback scores

## Product Considerations

### Insight Types Supported
- **Anomaly Detection**: Statistical outliers in test performance, execution time, failure rates
- **Trend Analysis**: Improving/degrading trends in quality metrics over time
- **Correlation Discovery**: Relationships between seemingly unrelated factors
- **Predictive Insights**: Forecasting future quality states based on historical patterns
- **Root Cause Analysis**: Identifying contributing factors to quality issues
- **Optimization Recommendations**: Suggestions for improving test efficiency or effectiveness

### Data Sources Supported
- **Test Execution Data**: Test results, execution times, pass/fail rates, flakiness metrics
- **Code Quality Metrics**: Static analysis results, complexity, coverage, duplication
- **Production Monitoring**: Error rates, latency, availability, user impact metrics
- **Process Metrics**: Deployment frequency, lead time, change failure rate, MTTR
- **User Feedback**: Test results, usability scores, satisfaction metrics
- **External Systems**: CI/CD pipeline metrics, issue tracking data, release metrics

### Insight Lifecycle Stages
- **Generation**: Insight created through analysis pipeline
- **Publication**: Insight made available to consumers via API/events
- **Consumption**: Users view and interact with insight
- **Feedback**: Users provide feedback on usefulness
- **Expiration**: Insight automatically or manually removed when outdated
- **Archival**: Expired insights moved to long-term storage for historical analysis

### Quality Metrics for Insights
- **Precision**: Percentage of insights that are actionable and correct
- **Recall**: Percentage of actual insights that are captured
- **Timeliness**: How quickly insights are generated after relevant data arrives
- **Novelty**: Percentage of insights that reveal new information
- **User Engagement**: Click-through rates, feedback provision rates
- **Action Rate**: Percentage of insights that lead to concrete actions/improvements