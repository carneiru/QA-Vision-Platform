# Organization Service

A service for managing organizations (tenants) and their hierarchical structure (projects, teams, users) in the QA Vision Platform's Platform domain.

## Overview

The Organization Service provides core multi-tenancy capabilities for the QEOS platform. It manages the organizational hierarchy that enables isolation, billing, and resource allocation across the platform. Organizations represent the top-level tenant entity, containing projects, teams, and users.

## Features

### ✅ Fully Implemented

- **Organization CRUD Operations**: Create, read, update, delete organizations
- **Hierarchy Management**: Manage projects, teams, and users within organizations
- **Role-Based Access Control (RBAC)**: Assign roles and permissions within organizational contexts
- **Multi-tenancy Enforcement**: Ensure data isolation between organizations
- **Organization Settings**: Configure organization-specific preferences and limits
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Health Checks**: Liveness and readiness probes for Kubernetes

### 🔧 Configuration Required

- **Database Configuration**: PostgreSQL connection settings
- **Security Configuration**: JWT secret, token expiration, algorithm
- **Service Discovery**: Configuration for inter-service communication
- **Caching**: Redis configuration for session and metadata caching
- **Event Streaming**: Kafka/Pulsar configuration for publishing organization events
- **External Identity Providers**: Configuration for LDAP, SAML, OAuth integrations

### 📝 Planned Enhancements

- **Hierarchical Billing**: Support for billing hierarchies and cost allocation
- **Advanced Org Structures**: Support for matrix organizations and cross-project teams
- **Audit Trail Enhancements**: Detailed change tracking for organizational modifications
- **Bulk Operations**: Import/export of organization hierarchies
- **Organization Templates**: Pre-configured organization structures for common use cases
- **Usage Analytics**: Reporting on resource consumption per organization

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 15+ (for organizational data storage)
- Redis 7.0+ (for caching and session storage)
- Apache Kafka 3.6+ or Apache Pulsar (for event streaming)
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/platforms/organization-service
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
- `APP_NAME`: Service name (default: "Organization Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token lifetime in days (default: 30)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
#### PostgreSQL (for organizational data)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "organization")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Redis Configuration
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (if required)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_CACHE_TTL_SECONDS`: Cache TTL in seconds (default: 300)

### Event Streaming Configuration
#### Apache Kafka/Pulsar
- `MESSAGE_BROKER_URL`: Message broker connection URL
- `ORGANIZATION_CREATED_TOPIC`: Topic for organization creation events
- `ORGANIZATION_UPDATED_TOPIC`: Topic for organization update events
- `ORGANIZATION_DELETED_TOPIC`: Topic for organization deletion events
- `ORGANIZATION_MEMBER_ADDED_TOPIC`: Topic for member addition events
- `ORGANIZATION_MEMBER_REMOVED_TOPIC`: Topic for member removal events

### Service Integration Configuration
- `AUTH_SERVICE_URL`: URL for Authentication Service (for token validation)
- `USER_SERVICE_URL`: URL for User Service (for user management)
- `PROJECT_SERVICE_URL`: URL for Project Service (for project operations)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Organization Management
- `GET /api/v1/organizations` - List organizations (with pagination, filtering)
  - Query params: `page`, `size`, `name`, `status`, `created_after`, `created_before`
- `POST /api/v1/organizations` - Create a new organization
- `GET /api/v1/organizations/{id}` - Get organization by ID
- `PUT /api/v1/organizations/{id}` - Update organization
- `DELETE /api/v1/organizations/{id}` - Soft delete organization
- `POST /api/v1/organizations/{id}/restore` - Restore soft-deleted organization

### Organization Hierarchy
- `GET /api/v1/organizations/{id}/projects` - Get projects in organization
- `POST /api/v1/organizations/{id}/projects` - Create project in organization
- `GET /api/v1/organizations/{id}/teams` - Get teams in organization
- `POST /api/v1/organizations/{id}/teams` - Create team in organization
- `GET /api/v1/organizations/{id}/users` - Get users in organization
- `POST /api/v1/organizations/{id}/users` - Add user to organization
- `DELETE /api/v1/organizations/{id}/users/{userId}` - Remove user from organization

### Role and Permission Management
- `GET /api/v1/organizations/{id}/roles` - Get roles in organization
- `POST /api/v1/organizations/{id}/roles` - Create role in organization
- `GET /api/v1/organizations/{id}/roles/{roleId}` - Get role by ID
- `PUT /api/v1/organizations/{id}/roles/{roleId}` - Update role
- `DELETE /api/v1/organizations/{id}/roles/{roleId}` - Delete role
- `POST /api/v1/organizations/{id}/roles/{roleId}/permissions` - Assign permission to role
- `DELETE /api/v1/organizations/{id}/roles/{roleId}/permissions/{permissionId}` - Remove permission from role

### Member Management
- `GET /api/v1/organizations/{id}/members` - Get organization members with roles
- `POST /api/v1/organizations/{id}/members` - Add member with role
- `PUT /api/v1/organizations/{id}/members/{memberId}` - Update member role
- `DELETE /api/v1/organizations/{id}/members/{memberId}` - Remove member

### Organization Settings
- `GET /api/v1/organizations/{id}/settings` - Get organization settings
- `PUT /api/v1/organizations/{id}/settings` - Update organization settings
- `POST /api/v1/organizations/{id}/settings/reset` - Reset settings to defaults

### Usage and Quotas
- `GET /api/v1/organizations/{id}/usage` - Get resource usage statistics
- `GET /api/v1/organizations/{id}/quotas` - Get quota limits
- `PUT /api/v1/organizations/{id}/quotas` - Update quota limits

## Request/Response Models

### Organization
- **Request/Response**: `Organization` (id, name, description, status, created_at, updated_at, owner_id, settings)

### Organization Creation Request
- **Request**: `OrganizationCreate` (name, description, owner_id, settings)

### Organization Update Request
- **Request**: `OrganizationUpdate` (name, description, status, settings)

### Project
- **Request/Response**: `Project` (id, name, description, identifier, status, color, start_date, end_date, created_at, updated_at, organization_id, owner_id)

### Team
- **Request/Response**: `Team` (id, name, description, created_at, updated_at, organization_id, created_by_id)

### User Membership
- **Request/Response**: `OrganizationMember` (id, user_id, role_id, joined_at, invited_by_id)

### Role
- **Request/Response**: `Role` (id, name, description, permissions, is_system, created_at, updated_at)

### Permission
- **Request/Response**: `Permission` (id, name, description, resource, action)

### Settings
- **Request/Response**: `OrganizationSettings` (key-value pairs for various organization-level configurations)

### Usage Statistics
- **Response**: `OrganizationUsage` (storage_used, api_calls_active_users, compute_hours, bandwidth_used)

### Quota Limits
- **Request/Response**: `OrganizationQuotas` (max_projects, max_teams, max_users, storage_limit_gb, api_rate_limit_per_hour)

## Dependencies

- **Authentication Service**: For validating user tokens and verifying permissions
- **User Service**: For retrieving user profile information when managing organization members
- **Project Service**: For coordinating project creation and lifecycle within organizations
- **Team Service**: For managing team structures within organizations
- **PostgreSQL**: Stores organization metadata, hierarchy, roles, permissions, and settings
- **Redis**: Caching layer for frequent organization lookups and session data
- **Apache Kafka/Pulsar**: Publishes organization lifecycle events for consumption by other domains
- **Shared Libraries**: Common utilities, authentication helpers, logging utilities
- **External Identity Providers** (Optional): LDAP, SAML, OAuth providers for organizational SSO

## Event Contracts

### Events Published
- `organization.created.v1` - When a new organization is created
- `organization.updated.v1` - When organization details are modified
- `organization.deleted.v1` - When an organization is soft-deleted
- `organization.restored.v1` - When a soft-deleted organization is restored
- `organization.member.added.v1` - When a user is added to an organization
- `organization.member.removed.v1` - When a user is removed from an organization
- `organization.role.created.v1` - When a new role is created within an organization
- `organization.role.updated.v1` - When a role is modified
- `organization.role.deleted.v1` - When a role is deleted
- `organization.setting.updated.v1` - When organization settings are modified
- `organization.quota.updated.v1` - When quota limits are changed

### Events Consumed
- `user.deleted.v1` - From User Service: Removes user from all organization memberships
- `user.role.changed.v1` - From Authentication Service: May trigger organization role reassessment
- `sso.user.federated.v1` - From Authentication Service: Auto-provisions user in appropriate organization
- `billing.account.created.v1` - From Billing Service: Creates organization linked to billing account
- `billing.account.updated.v1` - From Billing Service: Updates organization billing status

## Database Schema

### organizations Table
- `id`: UUID (Primary Key)
- `name`: String (Organization name)
- `description`: Text (Optional description)
- `status`: ENUM (active, suspended, pending_deletion, archived)
- `owner_id`: UUID (Reference to user who owns/organization)
- `settings`: JSONB (Organization-specific configuration)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `deleted_at`: Timestamp (Nullable, for soft delete)

### organization_projects Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `project_id`: UUID (Foreign Key to projects table)
- `role`: String (Role of organization in project: owner, member, viewer)
- `joined_at`: Timestamp

### organization_teams Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `team_id`: UUID (Foreign Key to teams table)
- `joined_at`: Timestamp

### organization_members Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `user_id`: UUID (Foreign Key to users table)
- `role_id`: UUID (Foreign Key to roles table)
- `joined_at`: Timestamp
- `invited_by_id`: UUID (Optional, who invited the user)

### organization_roles Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `name`: String (Role name)
- `description`: Text
- `permissions`: JSONB (Array of permission IDs)
- `is_system`: Boolean (Predefined system roles cannot be deleted)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### organization_permissions Table
- `id`: UUID (Primary Key)
- `name`: String (Permission name)
- `description`: Text
- `resource`: String (Resource this permission applies to)
- `action`: String (Action permitted: read, write, delete, execute, approve, share)

### organization_settings Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `key`: String (Setting key)
- `value`: JSONB (Setting value)
- `description`: Text
- `updated_at`: Timestamp

### organization_usage Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `period_start`: Timestamp (Start of usage period)
- `period_end`: Timestamp (End of usage period)
- `storage_used_bytes`: BigInt
- `api_calls_count`: Integer
- `active_users_count`: Integer
- `compute_hours`: Float
- `bandwidth_used_bytes`: BigInt
- `recorded_at`: Timestamp

### organization_quotas Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations)
- `max_projects`: Integer
- `max_teams`: Integer
- `max_users`: Integer
- `storage_limit_gb`: Integer
- `api_rate_limit_per_hour`: Integer
- `updated_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- JWT-based authentication with refresh token rotation
- Role-Based Access Control (RBAC) with hierarchical role inheritance
- Organization-scoped permissions ensuring users can only access resources within their organization
- Multi-tenancy enforcement at the database level (row-level security or query filtering)
- Service-to-service authentication for internal communications
- API key support for machine-to-machine integrations with scoped permissions

### Data Protection
- Organization ID included in all queries to enforce tenant isolation
- Sensitive settings (API keys, encryption keys) encrypted at rest using application-level encryption
- Audit logging for all organizational changes (who changed what and when)
- Regular security scanning of dependencies and container images
- GDPR-compliant data deletion and anonymization procedures

### Network Security
- Service mesh (Istio) enforces mTLS between all services
- Network policies restrict inter-service communication to authorized paths only
- Rate limiting and DDoS protection at the API gateway level
- Input validation and sanitization to prevent injection attacks

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI (async, high-performance)
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Caching**: Redis
- **Messaging**: Apache Kafka/Pulsar
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Validation**: Pydantic 2.0
- **Authentication**: PyJWT, Authlib, Python-SAML
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose
- **Orchestration**: Kubernetes with Helm charts

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Application Logic│    │ Infrastructure   │
│ (REST Endpoints)│    │ (Use Cases,      │    │ Layer              │
│                 │    │  Commands,       │    │ (Database, Cache,  │
│ └───────────────┘    │  Queries,        │    │  Messaging)        │
│                      │  Transactions)   │    └──────────────────┘
└─────────────────┘    └──────────────────┘             ▲
        ▲                         ▲                      │
        │                         │                      │
        │                         ▼                      │
        │               ┌──────────────────┐             │
        └──────────────►│ External Services│◄────────────┘
                        │ (Auth, User,     │
                        │  Project, Team)  │
                        └──────────────────┘
```

### Core Components Implementation

1. **API Layer**
   - RESTful endpoints following OpenAPI specification
   - Request validation using Pydantic models
   - Authentication middleware (JWT verification)
   - Authorization middleware (RBAC enforcement)
   - Input sanitization and output encoding
   - Rate limiting and request tracing

2. **Application Layer**
   - Use cases: Organization lifecycle management, hierarchy operations
   - Command/Query separation for complex operations
   - Transaction management for multi-operation workflows
   - Event publishing for state changes
   - Integration with external services (Auth, User, Project, Team)

3. **Domain Layer**
   - Organization aggregate root with hierarchy management
   - Value objects for settings, quotas, usage statistics
   - Domain events for internal communication within the service
   - Business rule validation (e.g., cannot delete organization with active projects)

4. **Infrastructure Layer**
   - SQLAlchemy ORM models with async support
   - Repository pattern for data access
   - Alembic migration scripts
   - Redis cache implementation with fallback strategies
   - Kafka producer/consumer configuration
   - External service clients (REST/gRPC)

### Data Flow

#### Organization Creation Flow
1. Client submits POST `/api/v1/organizations` with organization details
2. API layer validates request and extracts JWT claims
3. Application layer creates organization use case:
   - Validates user has permission to create organizations
   - Creates organization record in database
   - Sets up default roles (Owner, Admin, Member, Viewer)
   - Creates default settings
   - Publishes `organization.created.v1` event
4. Infrastructure persists data and publishes to Kafka
5. API returns organization details with HTTP 201

#### Member Addition Flow
1. Client posts to `/api/v1/organizations/{orgId}/members` with user_id and role_id
2. API validates JWT and checks if user has permission to manage members in org
3. Application layer verifies user and role exist, checks capacity limits
4. Creates organization_member record
5. Publishes `organization.member.added.v1` event
6. Returns member details

#### Cross-Service Integration
- When User Service publishes `user.deleted.v1`:
  - Organization Service consumes event
  - Removes user from all organization memberships
  - Publishes updated organization events if needed
- When Billing Service publishes `billing.account.created.v1`:
  - Organization Service creates organization linked to billing account
  - Sets initial quotas based on billing tier

## Running Tests

```bash
# Run unit tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_organization.py
pytest tests/test_membership.py
pytest tests/test_roles.py
pytest tests/test_events.py

# Run integration tests (requires running dependencies)
pytest -m integration
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database) with read replicas
- Deploy Redis cluster for high availability and persistence
- Use managed Kafka (Confluent Cloud, AWS MSK) or Pulsar service
- Implement proper resource limits and requests in Kubernetes
- Enable pod disruption budgets for high availability
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault) for sensitive configuration
- Implement backup and disaster recovery procedures for PostgreSQL
- Configure monitoring and alerting for key metrics (latency, error rates, resource usage)

### Scaling Considerations
- Horizontally scale API instances behind load balancer
- Redis clustering for cache scalability
- Database read replicas for query-heavy operations
- Partition organization data by ID hash for large-scale deployments
- Implement caching strategies for frequently accessed organization metadata
- Use CDN for serving static organization assets (logos, etc.)

### Data Integrity & Consistency
- ACID transactions for operations spanning multiple tables
- Eventual consistency model acceptable for cross-domain events
- Dead letter queue handling for failed event processing
- Idempotent event handlers to prevent duplicate processing
- Regular data consistency audits between services
- Backup strategies: daily snapshots, point-in-time recovery, geographic replication

## Maintenance

### Database Maintenance
```sql
-- Vacuum and analyze tables periodically
VACUUM ANALYZE organizations;
VACUUM ANALYZE organization_members;
VACUUM ANALYZE organization_roles;
VACUUM ANALYZE organization_usage;

-- Check for bloat and rebuild indexes if needed
SELECT schemaname, tablename, indexname, idx_bloat_ratio
FROM index_bloat
WHERE idx_bloat_ratio > 0.2;

-- Update index statistics
REINDEX TABLE occupations;
```

### Dependency Updates
```bash
# Check for outdated packages
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U

# Update specific package
pip install -U package-name
```

### Service Maintenance Tasks
- **Daily**: Check error rates, latency metrics, disk usage
- **Weekly**: Review slow query logs, update statistics
- **Monthly**: Security patch OS and dependencies, test backup restore
- **Quarterly**: Review access patterns, consider sharding/adjusting partitioning
- **Annually**: Capacity planning, disaster recovery drill

### Health Check Endpoints
- `GET /health` - Basic liveness check
- `GET /health/ready` - Readiness check (database connectivity, cache connectivity)
- `GET /health/live` - Liveness check (application responsiveness)
- `GET /health/detailed` - Comprehensive health including dependencies

## Product Considerations

### Data Types Supported
- **Organizations**: Top-level tenant containers with global unique identifiers
- **Projects**: Containers for test assets within organizations
- **Teams**: Cross-project groups for collaboration and resource sharing
- **Users**: Individuals belonging to one or more organizations
- **Roles**: Permission collections assignable to users/teams
- **Permissions**: Fine-grained access rights to specific resources and actions
- **Settings**: Organization-specific configuration key-value pairs
- **Usage Metrics**: Consumption tracking for billing and capacity planning
- **Quotas**: Resource limits preventing abusive consumption

### Collection Methods
- **Synchronous API**: Direct CRUD operations via REST endpoints
- **Asynchronous Events**: State changes propagated via Kafka/Pulsar topics
- **Batch Operations**: Bulk import/export for migration and synchronization
- **Webhooks**: HTTP callbacks for external system integration
- **GraphQL**: Optional GraphQL endpoint for flexible querying (planned)

### Integration Points
- **Service Instrumentation**: SDKs for automatic organization context propagation
- **Infrastructure Monitoring**: Integration with Prometheus/Grafana for resource metrics
- **Application Performance Monitoring**: Correlation with APM tools (Datadog, New Relic)
- **Audit Systems**: Forwarding of organizational change events to SIEM
- **Billing Systems**: Usage data export for consumption-based billing
- **Customer Relationship Management**: Synchronization with CRM platforms

### Data Retention and Tiering
- **Hot Storage**: Active organization data (current month) in primary database
- **Warm Storage**: Recent historical data (3-6 months) in read replicas
- **Cold Storage**: Archived organizational records (>6 months) in object storage
- **Configurable Policies**: Per-organization retention rules based on subscription tier
- **Automated Archiving**: Background processes moving old data to cheaper storage
- **Legal Hold**: Special handling for organizations under legal investigation