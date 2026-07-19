# Team Service

A service for managing teams, team memberships, roles, and permissions within organizations in the QA Vision Platform's Platform domain.

## Overview

The Team Service is responsible for the lifecycle management of teams and their associated memberships, roles, and permissions within the QEOS platform. It enables organizations to structure their users into logical groups (teams), assign granular permissions through role-based access control (RBAC), and manage hierarchical team structures. Teams serve as containers for users that can be assigned to projects, given access to resources, and used for notification distribution.

## Features

### ✅ Fully Implemented

- **Team CRUD Operations**: Create, read, update, delete teams within organizations
- **Hierarchical Team Structure**: Support for parent-child team relationships (nested teams)
- **Team Membership Management**: Add/remove users to/from teams with role assignments
- **Role-Based Access Control (RBAC)**: Define and assign roles with specific permissions within teams
- **Permission Management**: Grant/revoke permissions on team resources and operations
- **Team Settings Configuration**: Configure team-specific preferences and behaviors
- **Team Metadata & Tagging**: Extensible attributes for team classification and search
- **Team Activity Tracking**: Monitor team creation, modification, and membership changes
- **Bulk Operations**: Import/export team structures and memberships
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Health Checks**: Liveness and readiness probes for Kubernetes

### 🔧 Configuration Required

- **Database Configuration**: PostgreSQL connection settings
- **Security Configuration**: Encryption keys for sensitive team data
- **Team Structure Policies**: Maximum nesting depth, membership limits per team
- **Role & Permission System**: Default roles, permission inheritance rules
- **Notification Configuration**: Settings for team-wide notifications and alerts
- **Service Discovery**: Configuration for inter-service communication (Auth, Organization, User services)
- **Caching**: Redis configuration for team membership lookups and permission checks
- **Audit Logging**: Configuration for audit trail storage and retention
- **Quota Management**: Limits on number of teams, members, nested levels per organization

### 📝 Planned Enhancements

- **Dynamic Team Membership**: Automatic membership based on user attributes (rules engine)
- **Team Templates**: Predefined team structures for common use cases (dev, qa, ops, etc.)
- **Team Hierarchy Visualization**: Graphical representation of team structures
- **Team-based Notifications**: Configure notification routing to teams
- **Resource Quotas per Team**: Set and enforce resource usage limits by team
- **Team Lifecycle Management**: Archiving, restoration, and expiration policies
- **Cross-organization Teams**: Teams that span multiple organizations (with proper isolation)
- **Team Analytics**: Metrics on team activity, membership turnover, collaboration patterns
- **Permission Templates**: Reusable permission sets for common roles (team lead, member, lead, member, viewer)
- **Team Tags and Categories**: Taxonomy for team classification and discovery
- **Team-based SSO Group Mapping): Automatic team assignment based on SSO group membership

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 15+ (for team data storage)
- Redis 7.0+ (for caching membership checks)
- (Optional) Docker and Docker Compose
- (Optional) Organization Service and User Service must be running for full functionality

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/platforms/team-service
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

5. **Ensure dependencies are running**
   - Organization Service (for team organization context)
   - User Service (for user validation when adding members)

6. **Run the application**
   ```bash
   # Development mode
   python main.py
   
   # API will be available at http://localhost:8001
   # API documentation:
   # - Swagger UI: http://localhost:8001/api/v1/docs
   # - ReDoc: http://localhost:8001/api/v1/redoc
   ```

### Docker Deployment

```bash
docker-compose up --build
```

## Environment Variables

Copy `.env.example` to `.env` and configure as needed:

### Application Settings
- `APP_NAME`: Service name (default: "Team Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token lifetime in days (default: 30)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")
- `ENCRYPTION_KEY`: Key for encrypting sensitive team data (settings, metadata)

### Database Connection
#### PostgreSQL (for team data)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "team")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Redis Configuration
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (if required)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_MEMBERSHIP_TTL_SECONDS`: Team membership cache TTL in seconds (default: 300)
- `REDIS_PERMISSION_TTL_SECONDS)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_MEMBERSHIP_TTL_SECONDS`: Team membership cache TTL in seconds (default: 300)
- `REDIS_PERMISSION_TTL_SECONDS`: Permission check cache TTL in seconds (default: 60)
- `REDIS_TEAM_TTL_SECONDS`: Team data cache TTL in seconds (default: 600)

### Service Integration Configuration
- `AUTH_SERVICE_URL`: URL for Authentication Service (for token validation)
- `ORGANIZATION_SERVICE_URL`: URL for Organization Service (REQUIRED)
- `USER_SERVICE_URL`: URL for User Service (REQUIRED)
- `NOTIFICATION_SERVICE_URL`: URL for Notification Service (optional, for team alerts)
- `SHARED_SECRET_KEY`: Secret for service-to-service JWT signing (if used)

### Team Policies
- `MAX_TEAMS_PER_ORGANIZATION`: Maximum teams allowed per organization (default: 1000)
- `MAX_MEMBERS_PER_TEAM`: Maximum users per team (default: 5000)
- `MAX_TEAM_NESTING_DEPTH`: Maximum levels of team hierarchy (default: 10)
- `DEFAULT_TEAM_ROLE_ON_JOIN`: Default role assigned when user joins team (default: "member")
- `ALLOW_NESTED_TEAMS`: Whether to allow parent-child team relationships (default: True)
- `REQUIRE_UNIQUE_TEAM_NAMES_PER_ORG`: Whether team names must be unique within organization (default: True)
- `ALLOW_SELF_JOIN_TEAMS`: Whether users can request to join teams without approval (default: False)

### Feature Flags
- `ENABLE_DYNAMIC_MEMBERSHIP`: Enable rule-based automatic team membership (default: False)
- `ENABLE_TEAM_TEMPLATES`: Enable predefined team templates (default: False)
- `ENABLE_TEAM_QUOTAS`: Enable resource quotas per team (default: False)
- `ENABLE_TEAM_ARCHIVING`: Enable team archival instead of hard delete (default: True)
- `ENABLE_TEAM_EXPIRATION`: Enable automatic team expiration based on inactivity (default: False)
- `ENABLE_TEAM_TAGS`: Enable tagging system for teams (default: false)
- `ENABLE_TEAM_CATEGORIES`: Enable categorization system for teams (default: false)

### Audit Logging
- `AUDIT_LOG_ENABLED`: Enable audit logging (default: True)
- `AUDIT_LOG_RETENTION_DAYS`: Days to retain audit logs (default: 365)
- `AUDIT_STORAGE_TYPE`: `database`, `elasticsearch`, or `s3`

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000", "http://localhost:8001"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### Team Management
- `GET /api/v1/organizations/{orgId}/teams` - List teams in an organization (with pagination, filtering, sorting)
  - Query params: `page`, `size`, `name`, `parent_team_id`, `is_active`, `created_after`, `created_before`, `tags`
- `POST /api/v1/organizations/{orgId}/teams` - Create a new team in an organization
- `GET /api/v1/organizations/{orgId}/teams/{teamId}` - Get team by ID
- `PUT /api/v1/organizations/{orgId}/teams/{teamId}` - Update team
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}` - Soft delete team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/restore` - Restore soft-deleted team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/archive` - Archive team (if enabled)
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/unarchive` - Unarchive team (if enabled)
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/hierarchy` - Get team with full hierarchy (parents and children)
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/descendants` - Get all descendant teams
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/ancestors` - Get all ancestor teams

### Team Membership
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/members` - List team members (with pagination, filtering)
  - Query params: `page`, `size`, `user_id`, `role_id`, `is_active`, `joined_after`, `joined_before`
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members` - Add user to team
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}` - Get team membership details for user
- `PUT /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}` - Update team membership (role, status)
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}` - Remove user from team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}/reactivate` - Reactivate removed membership
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members/bulk-add` - Bulk add users to team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members/bulk-remove` - Bulk remove users from team
- `GET /api/v1/users/{userId}/teams` - Get all teams a user belongs to (across organizations)
- `GET /api/v1/organizations/{orgId}/users/{userId}/teams` - Get teams a user belongs to in specific organization

### Role & Permission Management
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/roles` - List roles defined for team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/roles` - Create new role for team
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/roles/{roleId}` - Get role details
- `PUT /api/v1/organizations/{orgId}/teams/{teamId}/roles/{roleId}` - Update role
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/roles/{roleId}` - Delete role (if not assigned)
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/permissions` - List permissions available for team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/permissions` - Create custom permission (if enabled)
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/permissions/{permissionId}` - Get permission details
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/roles/{roleId}/permissions` - Assign permission to role
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/roles/{roleId}/permissions/{permissionId}` - Revoke permission from role
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}/permissions` - Get effective permissions for user in team
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}/roles/{roleId}` - Assign role to user in team
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}/roles/{roleId}` - Remove role from user in team

### Team Settings & Metadata
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/settings` - Get team settings
- `PUT /api/v1/organizations/{orgId}/teams/{teamId}/settings` - Update team settings
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/metadata` - Get team metadata
- `PUT /api/v1/organizations/{orgId}/teams/{teamId}/metadata` - Update team metadata
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/tags` - Add tag to team
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/tags/{tag}` - Remove tag from team`
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/categories` - Get team categories
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/categories` - Add category to team
- `DELETE /api/v1/organizations/{orgId}/teams/{teamId}/categories/{category}` - Remove category from team

### Team Activity & Audit
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/activity` - Get team activity log
- `GET /api/v1/organizations/{orgId}/audit/teams` - Get team-related audit events (organization-wide)
- `GET /api/v1/organizations/{orgId}/audit/teams/{teamId}` - Get audit events for specific team

### Bulk Operations
- `POST /api/v1/organizations/{orgId}/teams/import` - Import teams from CSV/JSON (async)
- `GET /api/v1/organizations/{orgId}/teams/export` - Export teams to CSV/JSON (async)
- `POST /api/v1/organizations/{orgId}/teams/bulk-update` - Bulk update team attributes
- `POST /api/v1/organizations/{orgId}/teams/bulk-delete` - Bulk delete teams (soft delete)
- `POST /api/v1/organizations/{orgId}/teams/{teamId}/members/import` - Import team members from CSV/JSON
- `GET /api/v1/organizations/{orgId}/teams/{teamId}/members/export` - Export team members to CSV/JSON

### Team Statistics & Reporting
- `GET /api/v1/organizations/{orgId}/teams/stats/count` - Get total team count in organization
- `GET /api/v1/organizations/{orgId}/teams/stats/size-distribution` - Get distribution of team sizes
- `GET /api/v1/organizations/{orgId}/teams/stats/activity` - Get team activity metrics (creation, membership changes)
- `GET /api/v1/organizations/{orgId}/teams/stats/growth` - Get team growth trends over time
- `GET /api/v1/organizations/{orgId}/teams/stats/membership-overlap` - Get user membership overlap between teams
- `GET /api/v1/organizations/{orgId}/teams/stats/hierarchy-depth` - Get distribution of team hierarchy depths
- `GET /api/v1/organizations/{orgId}/teams/stats/role-distribution` - Get role assignment distribution across teams

## Request/Response Models

### Team
- **Request/Response**: `Team` (id, organization_id, name, description, parent_team_id, is_active, is_archived, created_at, updated_at, created_by_id)

### Team Creation Request
- **Request**: `TeamCreate` (name, description, parent_team_id=None, metadata={}, tags=[], settings={})

### Team Update Request
- **Request**: `TeamUpdate` (name, description, parent_team_id, metadata, tags, settings, is_active)

### Team Membership
- **Request/Response**: `TeamMembership` (id, team_id, user_id, role_id, is_active, joined_at, left_at, invited_by_id, invitation_status)
- **Add Member Request**: `TeamMemberAdd` (user_id, role_id, invited_by_id=None, invitation_message=None)
- **Update Membership Request**: `TeamMemberUpdate` (role_id, is_active)
- **User in Team Response**: `UserInTeam` (user details from User Service + membership info)

### Role & Permission
- **Request/Response**: `Role` (id, team_id, name, description, is_system_role, created_at, updated_at)
- **Role Creation Request**: `RoleCreate` (name, description, permissions=[])
- **Role Update Request**: `RoleUpdate` (name, description, is_active)
- **Permission Response**: `Permission` (id, team_id, name, description, resource, action, is_system_permission)
- **Permission Creation Request**: `PermissionCreate` (name, description, resource, action)
- **Permission Update Request**: `PermissionUpdate` (name, description, is_active)
- **Role Assignment**: `RoleAssignment` (role_id, user_id, team_id, assigned_at, assigned_by_id)
- **Permission Check Response**: `PermissionCheck` (has_permission, permission_name, granted_via_role_id, granted_via_inheritance)

### Team Settings & Metadata
- **Request/Response**: `TeamSettings` (notification_preferences, auto_approve_join_requests, require_mfa_for_admins, allow_external_members, data_retention_days, backup_frequency)
- **Request/Response**: `TeamMetadata` (key-value pairs for extensible attributes)
- **Tag Response**: `TeamTag` (team_id, tag, created_at)
- **Category Response**: `TeamCategory` (team_id, category, created_at)

### Bulk Operations
- **Import Request**: `TeamImportRequest` (format: csv/json, data: base64 encoded, create_missing_roles: boolean, send_welcome_notifications: boolean)
- **Export Request**: `TeamExportRequest` (format: csv/json, fields: list, filters: dict, include_members: boolean, include_hierarchy: boolean)
- **Bulk Update Request**: `TeamBulkUpdateRequest` (filters: dict, updates: dict)
- **Bulk Delete Request**: `TeamBulkDeleteRequest` (filters: dict, hard_delete: boolean, archive_instead: boolean)

### Activity & Audit
- **Activity Event**: `TeamActivity` (id, team_id, user_id, action_type, target_type, target_id, details, timestamp)
- **Audit Entry**: `TeamAudit` (id, team_id, user_id, action, changed_fields, old_values, new_values, timestamp, ip_address)

## Dependencies

- **Authentication Service**: For validating user sessions and issuing tokens (team service does NOT handle authentication)
- **Organization Service**: For validating organization context and enforcing organization-level policies
- **User Service**: For validating user existence and retrieving user details when managing memberships
- **Notification Service**: For sending team-wide notifications, membership invitations, and activity alerts
- **PostgreSQL**: Stores team structures, memberships, roles, permissions, settings, and metadata
- **Redis**: Caching layer for team membership lookups, permission checks, and frequently accessed team data
- **Shared Libraries**: Common utilities, encryption helpers, logging utilities, validation functions
- **External Systems** (Optional): LDAP/AD for group synchronization, SCIM provisioning systems

## Event Contracts

### Events Published
- `team.created.v1` - When a new team is created
- `team.updated.v1` - When team information is modified
- `team.deleted.v1` - When a team is soft-deleted
- `team.restored.v1` - When a soft-deleted team is restored
- `team.archived.v1` - When a team is archived (if enabled)
- `team.unarchived.v1` - When an archived team is unarchived (if enabled)
- `team.member.added.v1` - When a user is added to a team
- `team.member.removed.v1` - When a user is removed from a team
- `team.member.role.changed.v1` - When a user's role within a team is changed
- `team.member.status.changed.v1` - When a team membership is activated/deactivated
- `team.setting.changed.v1` - When team settings are modified
- `team.metadata.changed.v1` - When team metadata is updated
- `team.tag.added.v1` - When a tag is added to a team
- `team.tag.removed.v1` - When a tag is removed from a team
- `team.category.added.v1` - When a category is added to a team
- `team.category.removed.v1` - When a category is removed from a team
- `team.role.created.v1` - When a new role is created for a team
- `team.role.updated.v1` - When a team role is modified
- `team.role.deleted.v1` - When a team role is deleted
- `team.permission.assigned.v1` - When a permission is assigned to a role
- `team.permission.revoked.v1` - When a permission is revoked from a role
- `team.hierarchy.changed.v1` - When team parent-child relationship is modified
- `team.data.exported.v1` - When team data export is completed
- `team.data.deleted.v1` - When team data is permanently deleted

### Events Consumed
- `organization.created.v1` - From Organization Service: When organization is created (may trigger default team creation)
- `organization.updated.v1` - From Organization Service: When organization information is modified
- `organization.deleted.v1` - From Organization Service: When organization is soft-deleted (may trigger team archiving)
- `organization.restored.v1` - From Organization Service: When organization is restored
- `user.created.v1` - From User Service: When user is created (may trigger auto-assignment to default teams)
- `user.updated.v1` - From User Service: When user information is modified
- `user.deleted.v1` - From User Service: When user is soft-deleted (may trigger removal from teams)
- `user.restored.v1` - From User Service: When user is restored
- `auth.session.created.v1` - From Authentication Service: When user authenticates (may update last seen in teams)
- `notification.email.sent.v1` - From Notification Service: Delivery status of team notifications
- `notification.sms.sent.v1` - From Notification Service: Delivery status of team SMS alerts
- `audit.log.entry.v1` - From Audit Service: For centralized audit logging (if separate service)

## Database Schema

### teams Table
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key to organizations, Indexed)
- `name`: String (Indexed)
- `description`: Text (Nullable)
- `parent_team_id`: UUID (Foreign Key to teams, Nullable, Indexed)
- `is_active`: Boolean (Default: True)
- `is_archived`: Boolean (Default: False)
- `archived_at`: Timestamp (Nullable)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `created_by_id`: UUID (Foreign Key to users, Nullable)
- `settings`: JSONB (Team-specific configuration)
- `metadata`: JSONB (Extensible key-value pairs)

### team_memberships Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `user_id`: UUID (Foreign Key to users, Indexed)
- `role_id`: UUID (Foreign Key to team_roles, Nullable, Indexed)
- `is_active`: Boolean (Default: True)
- `joined_at`: Timestamp
- `left_at`: Timestamp (Nullable)
- `invited_by_id`: UUID (Foreign Key to users, Nullable)
- `invitation_status`: ENUM (pending, accepted, rejected, expired)
- `invitation_expires_at`: Timestamp (Nullable)
- `invitation_message`: Text (Nullable)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### team_roles Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `name`: String (Unique per team)
- `description`: Text (Nullable)
- `is_system_role`: Boolean (Default: False - roles like "owner", "admin" may be system-defined)
- `permissions`: JSONB (Array of permission IDs or permission objects)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### team_permissions Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `name`: String (Unique per team)
- `description`: Text (Nullable)
- `resource`: String (e.g., "project", "artifact", "environment", "test_run")
- `action`: String (e.g., "read", "write", "delete", "execute", "approve")
- `is_system_permission`: Boolean (Default: False)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### team_tags Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `tag`: String (Indexed)
- `created_at`: Timestamp
- `created_by_id`: UUID (Foreign Key to users, Nullable)

### team_categories Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `category`: String (Indexed)
- `created_at`: Timestamp
- `created_by_id`: UUID (Foreign Key to users, Nullable)

### team_activity Table
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams, Indexed)
- `user_id`: UUID (Foreign Key to users, Nullable - system actions may not have user)
- `action_type`: ENUM (created, updated, deleted, member_added, member_removed, role_changed, setting_changed, metadata_changed)
- `target_type`: ENUM (team, membership, role, permission, setting, metadata)
- `target_id`: UUID (Nullable, references appropriate table based on target_type)
- `details`: JSONB (Action-specific details)
- `timestamp`: Timestamp
- `ip_address`: String (Nullable)
- `user_agent`: Text (Nullable)

### team_audit Table (if using database for audit)
- `id`: UUID (Primary Key)
- `team_id`: UUID (Foreign Key to teams)
- `user_id`: UUID (Foreign Key to users - who made the change)
- `action`: String (CREATE_TEAM, UPDATE_TEAM, DELETE_TEAM, ADD_MEMBER, REMOVE_MEMBER, CHANGE_ROLE, etc.)
- `changed_fields`: JSONB (Array of field names that were modified)
- `old_values`: JSONB (Values before change)
- `new_values`: JSONB (Values after change)
- `performed_via`: String (API, WEB, MOBILE, API_KEY)
- `ip_address`: String (Nullable)
- `user_agent`: Text (Nullable)
- `created_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- The Team Service does NOT perform authentication; it validates JWTs from the Authentication Service
- Service-to-service communication uses short-lived JWTs signed with a shared secret
- Direct API access requires valid JWT with appropriate scopes (team:read, team:write, team:admin)
- Role-Based Access Control (RBAC) at multiple levels:
  - Organization Level: Users must have appropriate permissions in the organization to manage teams
  - Team Level: Users must have appropriate permissions within a team to manage its resources
  - Resource Level: Specific permissions control what actions users can perform on team resources
- Permission model combines:
  - Team Roles: Predefined sets of permissions assigned to users within a team
  - Direct Permissions: Specific permissions granted directly to users (less common, usually for overrides)
  - Permission Inheritance: Child teams inherit permissions from parent teams (configurable)
- Service API endpoints enforce:
  - `team:read`: View teams and basic membership information
  - `team:write`: Create/update teams, manage settings and metadata
  - `team:admin`: Full team management (delete, archive, manage hierarchy)
  - `team:membership:read`: View team members and their roles
  - `team:membership:write`: Add/remove members, change roles
  - `team:role:manage`: Create/update/delete team roles
  - `team:permission:manage`: Create/update/delete team permissions
  - `team:member:role:assign`: Assign/revoke roles to/from members
- Passwords are NOT handled by this service (delegated to Authentication and User Services)
- API keys and other sensitive credentials are encrypted at rest using AES-256-GCM
- All sensitive configuration data is encrypted in the database using application-level encryption
- Regular key rotation for encryption keys (with versioned data to allow gradual migration)

### Data Protection
- Principle of least privilege: Users only receive team data they are authorized to see
- Data minimization: Only essential team information is stored
- Purpose limitation: Team data is only used for authorization and organization purposes
- Storage limitation: Data retention policies with archiving instead of deletion when possible
- Integrity and confidentiality: TLS encryption for all data in transit, encryption at rest for sensitive data
- Accountability: Comprehensive audit logging of all team data access and modifications
- Team isolation: Strict enforcement that users can only access teams within organizations they belong to

### Network Security
- Service mesh (Istio) enforces mTLS between all services
- Network policies restrict communication to only required services (Auth, Org, User, Notification)
- Rate limiting and brute force protection on membership modification endpoints
- Input validation and sanitization to prevent injection attacks
- Secure headers (CSP, HSTS, X-Frame-Options, etc.) on all HTTP responses
- Regular vulnerability scanning of dependencies and container images
- API endpoint timeout protection to prevent resource exhaustion

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI (async, high-performance)
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Caching**: Redis
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Validation**: Pydantic 2.0
- **Encryption**: Cryptography library (Fernet for symmetric encryption, RSA for key wrapping)
- **Testing**: Pytest with coverage reporting, factory-boy for test data, faker for realistic test data
- **CI/CD**: GitHub Actions for build, test, security scanning (bandit, safety), and container image building
- **Containerization**: Docker and Docker Compose
- **Orchestration**: Kubernetes with Helm charts
- **Logging**: Structured logging (JSON) with correlation IDs
- **Monitoring**: Prometheus metrics endpoint, OpenTelemetry for tracing

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Application Logic│    │ Infrastructure   │
│ (REST Endpoints)│    │ (Use Cases,      │    │ Layer              │
│                 │    │  Commands,       │    │ (Database, Cache,  │
│ └───────────────┘    │  Queries,        │    │  Encryption)       │
│                      │  Transactions)   │    └──────────────────┘
└─────────────────┘    └──────────────────┘             ▲
        ▲                         ▲                      │
        │                         │                      │
        │                         ▼                      │
        │               ┌──────────────────┐             │
        └──────────────►│ External Services│◄────────────┘
                        │ (Auth, Org, User,│
                        │  Notification)   │
                        └──────────────────┘
```

### Core Components Implementation

1. **API Layer**
   - RESTful endpoints following OpenAPI specification
   - Request validation using Pydantic models with custom validators for hierarchical constraints
   - Authentication middleware (JWT verification for service-to-service)
   - Authorization middleware (multi-level RBAC: organization → team → resource)
   - Input validation (preventing circular team hierarchies, validating user/org existence)
   - Output formatting (consistent response structures, proper error handling)
   - Rate limiting (per organization, per team, per user)
   - Request/response logging with correlation IDs for tracing
   - Exception handling with standardized error responses and correlation IDs

2. **Application Layer**
   - Use cases: Team lifecycle management, membership operations, role/permission management
   - Transaction management for multi-step operations (team creation with default roles)
   - Hierarchy validation (preventing circular references, enforcing max nesting depth)
   - Membership validation (checking user exists in organization, preventing duplicate active memberships)
   - Role and permission validation (checking for permission conflicts, preventing privilege escalation)
   - Event publishing for state changes (using outsider pattern to avoid coupling)
   - Validation business rules (team name uniqueness per org, role name uniqueness per team)
   - Integration with external services (user validation, org context, notifications)
   - Background job handling for asynchronous operations (exports, imports, bulk operations, hierarchy recalculations)

3. **Domain Layer**
   - Team aggregate root with encapsulated business logic for hierarchy management
   - Value objects for team names, descriptions, settings
   - Domain events for internal communication (TeamCreated, MemberAdded, RoleAssigned, etc.)
   - Specifications for complex validation rules (no circular hierarchies, valid membership transitions)
   - Factories for creating team instances (new team, team with hierarchy, template-based team)
   - Repositories for data access abstraction (TeamRepository, MembershipRepository, RoleRepository, etc.)
   - Permission engine for evaluating effective permissions (considering roles, direct assignments, inheritance)

4. **Infrastructure Layer**
   - SQLAlchemy ORM models with defined relationships, constraints, and cascading rules
   - Repository implementations with caching layers and fallback strategies
   - Alembic migration scripts with data migration capabilities for schema evolution
   - Redis cache implementation with serialization strategies, cache warming, and fallback to DB
   - Encryption services for sensitive data (team settings, metadata, invitation tokens)
   - External service clients with circuit breaker, retry, and timeout policies
   - Hierarchy management utilities (path enumeration, depth calculation, subtree operations)
   - Permission evaluation engine with caching and inheritance resolution
   - Background workers using RQ or Celery for asynchronous processing
   - Health check endpoints for liveness, readiness, and deep dependency checks

### Data Flow

#### Team Creation Flow
1. Client submits POST `/api/v1/organizations/{orgId}/teams` with team details (name, description, parent_team_id)
2. API layer validates request structure, checks JWT for org:team:create permission
3. Application layer creates team use case:
   - Validates organization exists and user has permission to create teams in it
   - Checks team name uniqueness within organization (if required)
   - Validates parent_team_id exists in same organization (if provided) and checks nesting depth
   - Creates team record in database
   - Creates default roles for team (if configured: owner, admin, member)
   - Applies default team settings
   - Publishes `team.created.v1` event
4. Infrastructure persists data in atomic transaction
5. API returns team object with HTTP 201

#### Adding Member to Team Flow
1. Client posts to `/api/v1/organizations/{orgId}/teams/{teamId}/members` with user_id and role_id
2. API layer validates JWT and checks if user has team:membership:write permission on team
3. Application layer adds member use case:
   - Validates team exists and is active
   - Validates user exists (via User Service call) and is active in organization
   - Validates role exists and is active in team
   - Checks if user already has active membership in team (prevents duplicates)
   - Checks membership limits for team and organization
   - Creates membership record with invited_by_id set to current user (if not self-add)
   - Sends invitation notification via Notification Service (if not auto-accept)
   - Publishes `team.member.added.v1` event
4. Atomic database update
5. Returns membership object with HTTP 201

#### Permission Check Flow
1. Client calls `/api/v1/organizations/{orgId}/teams/{teamId}/members/{userId}/permissions` or internal service check
2. Application layer evaluates permissions:
   - Retrieves all active roles for user in team
   - Collects permissions from those roles
   - Checks for direct permission assignments to user in team
   - Resolves permission inheritance from parent teams (if enabled)
   - Combines and deduplicates permissions
   - Checks if requested permission is in the final set
3. Returns permission decision with granting details
4. Uses Redis caching for frequent permission checks (user+team+permission combinations)

#### Team Hierarchy Operations
- **Getting Descendants**: Recursive CTE or application-level traversal with depth limiting
- **Moving Team**: Validate new parent exists in same org, check for circular references, update parent_team_id
- **Permission Inheritance**: When checking permissions, traverse up hierarchy collecting permissions from inherited roles
- **Bulk Operations**: When performing operations on parent team, optionally apply to all descendants (with confirmation)

#### Cross-Service Integration
- When Organization Service publishes `organization.deleted.v1`:
  - Team Service archives all teams in organization (if archiving enabled) or marks for deletion
- When Organization Service publishes `organization.updated.v1`:
  - Team Service updates organization_id in cache if organization identifier changed
- When User Service publishes `user.deleted.v1`:
  - Team Service removes user from all teams (sets memberships to inactive, sends notifications)
  - May trigger team cleanup if team becomes empty and configured to auto-delete
- When Notification Service publishes `notification.email.sent.v1`:
  - Team Service updates invitation status if this was a team invitation email
- When Authentication Service publishes `auth.session.created.v1`:
  - Team Service may update user's last seen timestamp in teams they belong to

## Running Tests

```bash
# Run unit tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_team.py
pytest tests/test_membership.py
pytest tests/test_role.py
pytest tests/test_permission.py
@pytest.mark.integration
pytest -m integration

# Run security tests
pytest -m security

# Run performance tests
pytest -m performance

# Run hierarchy-specific tests
pytest -m hierarchy

# Run permission engine tests
pytest -m permissions
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database) with:
  - Automated backups
  - Point-in-time recovery
  - Read replicas for scaling read queries (team lookups are frequent)
  - Multi-AZ deployment for high availability
- Deploy Redis cluster for high availability and automatic failover (critical for permission checks)
- Implement proper resource limits and requests in Kubernetes