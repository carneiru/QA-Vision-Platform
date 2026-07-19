# User Service

A service for managing user profiles, authentication credentials, and identity-related attributes in the QA Vision Platform's Platform domain.

## Overview

The User Service is responsible for the lifecycle management of user identities within the QEOS platform. It handles user profile information, authentication credentials (hashed passwords, API keys, tokens), identity verification, and user preferences. This service does not handle authentication logic itself (that is delegated to the Authentication Service), but rather maintains the user identity data that other services consume.

## Features

### ✅ Fully Implemented

- **User CRUD Operations**: Create, read, update, delete user profiles
- **Profile Management**: Handle user attributes (name, email, contact information, preferences)
- **Authentication Credential Management**: Secure storage and rotation of password hashes, API keys, and token secrets
- **Identity Verification**: Email/phone verification workflows and status tracking
- **User Preferences**: Storage and retrieval of user-specific settings and configurations
- **User Status Management**: Active, suspended, pending verification, deactivated states
- **Bulk Operations**: Import/export of user data for migration and synchronization
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Health Checks**: Liveness and readiness probes for Kubernetes

### 🔧 Configuration Required

- **Database Configuration**: PostgreSQL connection settings
- **Security Configuration**: Password hashing parameters (bcrypt cost), encryption keys for sensitive data
- **Token Configuration**: JWT settings for service-to-service token generation (if applicable)
- **Email/SMS Providers**: Configuration for verification notifications (SMTP, Twilio, etc.)
- **Service Discovery**: Configuration for inter-service communication (Auth, Organization, Team services)
- **Caching**: Redis configuration for user session data and frequently accessed profiles
- **Audit Logging**: Configuration for audit trail storage and retention
- **Privacy Controls**: Settings for data anonymization and deletion compliance (GDPR, CCPA)

### 📝 Planned Enhancements

- **Social Identity Federation**: Integrated support for OAuth/OpenID Connect providers (Google, GitHub, Azure AD)
- **Multi-Factor Authentication (MFA)**: TOTP, SMS, and hardware key management
- **User Self-Service Portal**: Profile management, password reset, connected accounts
- **Bulk User Operations**: Advanced import/export with validation and deduplication
- **User Activity Tracking**: Last login, IP address, device fingerprinting (with privacy controls)
- **Data Export/Deletion**: Automated GDPR compliance workflows
- **Role-Based Access Control (RBAC) Integration**: Direct assignment of global roles (beyond project/team scope)
- **User Segmentation**: Dynamic groups based on attributes for targeted communications
- **Account Linking**: Ability to link multiple identities (email, username, social) to a single user record

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 15+ (for user data storage)
- Redis 7.0+ (for session caching and temporary data)
- (Optional) Docker and Docker Compose
- (Optional) Email service (SMTP SendGrid, Mailgun) or SMS provider (Twilio) for verification

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/platforms/user-service
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

5. **Optional: Set up email/SMS providers for verification (development)**
   - For development, you can use services like Mailtrap or Twilio trial accounts
   - Or disable verification requirements in configuration for local testing

6. **Run the application**
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
- `APP_NAME`: Service name (default: "User Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 60)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token lifetime in days (default: 30)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")
- `PASSWORD_HASH_BCRYPT_COST`: Bcrypt cost factor (default: 12)
- `ENCRYPTION_KEY`: Key for encrypting sensitive user data (API keys, etc.)

### Database Connection
#### PostgreSQL (for user data)
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "user")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Redis Configuration
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (if required)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_SESSION_TTL_SECONDS`: Session TTL in seconds (default: 1800)
- `REDIS_CACHE_TTL_SECONDS`: Cache TTL in seconds (default: 300)

### Email Configuration (for verification)
- `EMAIL_PROVIDER`: `smtp`, `sendgrid`, `mailgun`, or `console` (for dev)
- `SMTP_HOST`: SMTP server host
- `SMTP_PORT`: SMTP server port
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAIL_FROM`: From address for outgoing emails
- `EMAIL_FROM_NAME`: From name for outgoing emails

### SMS Configuration (for verification)
- `SMS_PROVIDER`: `twilio`, `nexmo`, or `console` (for dev)
- `TWILIO_ACCOUNT_SID`: Twilio account SID
- `TWILIO_AUTH_TOKEN`: Twilio auth token
- `TWILIO_FROM_NUMBER`: Twilio phone number for sending SMS

### Service Integration Configuration
- `AUTH_SERVICE_URL`: URL for Authentication Service (for token validation)
- `ORGANIZATION_SERVICE_URL`: URL for Organization Service
- `TEAM_SERVICE_URL`: URL for Team Service
- `SHARED_SECRET_KEY`: Secret for service-to-service JWT signing (if used)

### Audit Logging
- `AUDIT_LOG_ENABLED`: Enable audit logging (default: True)
- `AUDIT_LOG_RETENTION_DAYS`: Days to retain audit logs (default: 365)
- `AUDIT_STORAGE_TYPE`: `database`, `elasticsearch`, or `s3`

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with service information

### User Management
- `GET /api/v1/users` - List users (with pagination, filtering, sorting)
  - Query params: `page`, `size`, `email`, `status`, `created_after`, `created_before`, `is_superuser`
- `POST /api/v1/users` - Create a new user
- `GET /api/v1/users/{id}` - Get user by ID
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Soft delete user
- `POST /api/v1/users/{id}/restore` - Restore soft-deleted user
- `POST /api/v1/users/{id}/deactivate` - Deactivate user (revoke sessions)
- `POST /api/v1/users/{id}/activate` - Reactivate user

### Authentication Credentials
- `POST /api/v1/users/{id}/password` - Set/change password (requires current password or admin)
- `POST /api/v1/users/{id}/password/reset` - Initiate password reset (token via email/SMS)
- `POST /api/v1/users/{id}/password/reset/confirm` - Confirm password reset with token
- `POST /api/v1/users/{id}/api-key` - Generate new API key
- `GET /api/v1/users/{id}/api-key` - List API keys (masked)
- `DELETE /api/v1/users/{id}/api-key/{keyId}` - Revoke API key
- `POST /api/v1/users/{id}/mfa/enable` - Enable multi-factor authentication
- `POST /api/v1/users/{id}/mfa/disable` - Disable multi-factor authentication
- `POST /api/v1/users/{id}/mfa/verify` - Verify MFA challenge

### User Profile & Preferences
- `GET /api/v1/users/{id}/profile` - Get user profile details
- `PUT /api/v1/users/{id}/profile` - Update user profile
- `GET /api/v1/users/{id}/preferences` - Get user preferences
- `PUT /api/v1/users/{id}/preferences` - Update user preferences
- `POST /api/v1/users/{id}/preferences/reset` - Reset preferences to defaults

### User Status & Verification
- `GET /api/v1/users/{id}/verification-status` - Get email/phone verification status
- `POST /api/v1/users/{id}/verify-email` - Send email verification link
- `POST /api/v1/users/{id}/verify-phone` - Send SMS verification code
- `POST /api/v1/users/{id}/verify-email/confirm` - Confirm email verification with token
- `POST /api/v1/users/{id}/verify-phone/confirm` - Confirm phone verification with code
- `GET /api/v1/users/{id}/sessions` - List active user sessions
- `DELETE /api/v1/users/{id}/sessions/{sessionId}` - Revoke specific session
- `DELETE /api/v1/users/{id}/sessions` - Revoke all sessions except current

### Bulk Operations
- `POST /api/v1/users/import` - Import users from CSV/JSON (async)
- `GET /api/v1/users/export` - Export users to CSV/JSON (async)
- `POST /api/v1/users/bulk-update` - Bulk update user attributes
- `POST /api/v1/users/bulk-delete` - Bulk delete users (soft delete)

### User Statistics & Reporting
- `GET /api/v1/users/stats/count` - Get total user count (with filters)
- `GET /api/v1/users/stats/registration-trends` - Get user registration trends over time
- `GET /api/v1/users/stats/active-users` - Get daily/weekly/monthly active users
- `GET /api/v1/users/stats/geographic` - Get user distribution by geography (if IP data collected)

## Request/Response Models

### User
- **Request/Response**: `User` (id, email, username, first_name, last_name, display_name, is_active, is_superuser, is_verified, created_at, updated_at, last_login_at)

### User Creation Request
- **Request**: `UserCreate` (email, username, password, first_name, last_name, is_superuser=False)

### User Update Request
- **Request**: `UserUpdate` (first_name, last_name, display_name, is_active)

### User in Database (Internal)
- **Response**: `UserInDB` (extends User with hashed_password, api_keys_encrypted, mfa_secrets_encrypted, etc.)

### User Credentials
- **Password Change Request**: `PasswordChange` (current_password, new_password)
- **Password Reset Request**: `PasswordResetRequest` (email_or_username)
- **Password Reset Confirm**: `PasswordResetConfirm` (token, new_password)
- **API Key Response**: `APIKeyResponse` (id, name, key_prefix, created_at, expires_at, last_used_at)
- **MFA Setup Response**: `MFASetupResponse` (secret, qr_code_uri, backup_codes)

### User Profile
- **Request/Response**: `UserProfile` (avatar_url, bio, website, location, timezone, language, date_format, time_format)

### User Preferences
- **Request/Response**: `UserPreferences` (ui_theme, notification_preferences, privacy_settings, dashboard_layout)

### Verification
- **Verification Request**: `VerificationRequest` (email_or_username)
- **Verification Confirmation**: `VerificationConfirmation` (token)
- **Verification Response**: `VerificationResponse` (message, expires_in)

### User Session
- **Request/Response**: `UserSession` (id, ip_address, user_agent, created_at, last_used_at, is_current)

### Bulk Operations
- **Import Request**: `UserImportRequest` (format: csv/json, data: base64 encoded, send_welcome_email: boolean)
- **Export Request**: `UserExportRequest` (format: csv/json, fields: list, filters: dict)
- **Bulk Update Request**: `UserBulkUpdateRequest` (filters: dict, updates: dict)
- **Bulk Delete Request**: `UserBulkDeleteRequest` (filters: dict, hard_delete: boolean)

## Dependencies

- **Authentication Service**: For validating user sessions and issuing tokens (user service does NOT handle authentication)
- **Organization Service**: For linking users to organizations and checking organizational permissions
- **Team Service**: For managing team memberships associated with users
- **Notification Service**: For sending verification emails/SMS and security alerts
- **PostgreSQL**: Stores user profiles, credentials (hashed), preferences, and metadata
- **Redis**: Caching layer for user sessions, authentication tokens, and frequently accessed profiles
- **Email/SMS Providers**: For sending verification codes and notifications (SMTP, SendGrid, Mailgun, Twilio, etc.)
- **Shared Libraries**: Common utilities, encryption helpers, logging utilities, validation functions
- **External Identity Providers** (Optional): LDAP, SAML endpoints for federated authentication (when integrated)

## Event Contracts

### Events Published
- `user.created.v1` - When a new user is created
- `user.updated.v1` - When user profile information is modified
- `user.deleted.v1` - When a user is soft-deleted
- `user.restored.v1` - When a soft-deleted user is restored
- `user.deactivated.v1` - When a user is deactivated
- `user.reactivated.v1` - When a deactivated user is reactivated
- `user.password.changed.v1` - When user password is changed
- `user.password.reset.v1` - When password reset is initiated
- `user.password.reset.completed.v1` - When password reset is completed
- `user.email.verification.initiated.v1` - When email verification is started
- `user.email.verified.v1` - When email verification is completed
- `user.phone.verification.initiated.v1` - When phone verification is started
- `user.phone.verified.v1` - When phone verification is completed
- `user.api.key.created.v1` - When an API key is generated
- `user.api.key.revoked.v1` - When an API key is revoked
- `user.mfa.enabled.v1` - When multi-factor authentication is enabled
- `user.mfa.disabled.v1` - When multi-factor authentication is disabled
- `user.login.v1` - When user successfully logs in (from Auth Service)
- `user.logout.v1` - When user logs out (from Auth Service)
- `user.session.created.v1` - When a new session is established
- `user.session.ended.v1` - When a session ends (explicit logout or timeout)
- `user.data.exported.v1` - When user data export is completed
- `user.data.deleted.v1` - When user data is permanently deleted (GDPR right to be forgotten)

### Events Consumed
- `organization.user.added.v1` - From Organization Service: When user is added to organization (may trigger welcome email)
- `organization.user.removed.v1` - From Organization Service: When user is removed from organization (may trigger offboarding)
- `team.member.added.v1` - From Team Service: When user is added to team
- `team.member.removed.v1` - From Team Service: When user is removed from team
- `auth.session.created.v1` - From Authentication Service: When user authenticates (update last login)
- `auth.session.ended.v1` - From Authentication Service: When user session ends (cleanup)
- `auth.token.refresh.v1` - From Authentication Service: When token is refreshed (update last used)
- `audit.log.entry.v1` - From Audit Service: For centralized audit logging (if separate service)
- `notification.email.sent.v1` - From Notification Service: Delivery status of emails
- `notification.sms.sent.v1` - From Notification Service: Delivery status of SMS

## Database Schema

### users Table
- `id`: UUID (Primary Key)
- `email`: String (Unique, Indexed)
- `username`: String (Unique, Indexed)
- `first_name`: String
- `last_name`: String
- `display_name`: String
- `is_active`: Boolean (Default: True)
- `is_superuser`: Boolean (Default: False)
- `is_verified`: Boolean (Default: False - email verification)
- `phone_number`: String (Nullable, Unique if provided)
- `phone_verified`: Boolean (Default: False)
- `avatar_url`: String (Nullable)
- `bio`: Text (Nullable)
- `website`: String (Nullable)
- `location`: String (Nullable)
- `timezone`: String (Default: UTC)
- `language`: String (Default: en)
- `date_format`: String (Default: YYYY-MM-DD)
- `time_format`: String (Default: 24h)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `last_login_at`: Timestamp (Nullable)
- `deleted_at`: Timestamp (Nullable, for soft delete)

### user_credentials Table
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key to users, Unique)
- `password_hash`: String (Bcrypt hash)
- `password_changed_at`: Timestamp
- `password_expires_at`: Timestamp (Nullable)
- `password_reset_token`: String (Nullable, Indexed)
- `password_reset_expires_at`: Timestamp (Nullable)
- `api_keys_encrypted`: JSONB (Encrypted array of API key objects: {id, name, key_prefix, created_at, expires_at, last_used_at})
- `mfa_secrets_encrypted`: JSONB (Encrypted object for TOTP/HOTP secrets and backup codes)
- `webauthn_credentials_encrypted`: JSONB (Encrypted WebAuthn credential IDs and public keys)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### user_preferences Table
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key to users, Unique)
- `ui_theme`: String (light, dark, auto)
- `notification_email`: Boolean (Default: True)
- `notification_sms`: Boolean (Default: False)
- `notification_push`: Boolean (Default: False)
- `email_frequency`: String (immediate, daily, weekly)
- `privacy_profile_visible`: Boolean (Default: True)
- `privacy_show_online_status`: Boolean (Default: True)
- `dashboard_widgets`: JSONB (Array of widget configurations)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### user_sessions Table
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key to users)
- `session_token`: String (Unique, Indexed)
- `ip_address`: String (Nullable)
- `user_agent`: Text (Nullable)
- `created_at`: Timestamp
- `last_used_at`: Timestamp
- `expires_at`: Timestamp
- `is_active`: Boolean

### user_verification Table
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key to users)
- `type`: ENUM (email, phone)
- `value`: String (email address or phone number)
- `token`: String (Unique, Indexed)
- `expires_at`: Timestamp
- `verified_at`: Timestamp (Nullable)
- `created_at`: Timestamp
- `attempts`: Integer (Default: 0)
- `max_attempts`: Integer (Default: 5)

### user_audit Table (if using database for audit)
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key to users)
- `action`: String (CREATE, UPDATE, DELETE, LOGIN, LOGOUT, PASSWORD_CHANGE, etc.)
- `changed_fields`: JSONB (Array of field names that were modified)
- `old_values`: JSONB (Values before change)
- `new_values`: JSONB (Values after change)
- `performed_by_id`: UUID (Nullable, Foreign Key to users - who made the change)
- `performed_via`: String (API, WEB, MOBILE, API_KEY)
- `ip_address`: String (Nullable)
- `user_agent`: Text (Nullable)
- `created_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- The User Service does NOT perform authentication; it manages identity data used by the Authentication Service
- Service-to-service communication uses short-lived JWTs signed with a shared secret
- Direct API access requires valid JWT with appropriate scopes (user:read, user:write, user:admin)
- Role-Based Access Control (RBAC) at the service level:
  - `user:read`: Read user profiles (non-sensitive data)
  - `user:write`: Update user profiles and preferences
  - `user:admin`: Full user management (create, delete, manage credentials)
  - `user:credential:read`: View credential metadata (hashed passwords not included)
  - `user:credential:write`: Manage credentials (passwords, API keys, MFA)
  - `user:verification:manage`: Initiate and confirm verification processes
- Passwords are hashed using bcrypt with configurable cost factor
- API keys are generated using cryptographically secure random bytes (32 bytes) and stored encrypted
- MFA secrets are encrypted at rest using AES-256-GCM
- All sensitive data fields are encrypted in the database using application-level encryption
- Regular key rotation for encryption keys (with versioned data to allow gradual migration)

### Data Protection
- Principle of least privilege: Services only receive the user data they need
- Data minimization: Only essential user information is stored; sensitive data is encrypted
- Purpose limitation: User data is only used for the purposes specified at collection
- Storage limitation: Data retention policies with automated purging of inactive accounts
- Integrity and confidentiality: TLS encryption for all data in transit, encryption at rest for sensitive data
- Accountability: Comprehensive audit logging of all user data access and modifications

### Network Security
- Service mesh (Istio) enforces mTLS between all services
- Network policies restrict communication to only required services
- Rate limiting and brute force protection on credential-related endpoints
- Input validation and sanitization to prevent injection attacks
- Secure headers (CSP, HSTS, X-Frame-Options, etc.) on all HTTP responses
- Regular vulnerability scanning of dependencies and container images

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
- **Password Hashing**: Bcrypt
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
                        │ (Auth, Org, Team,│
                        │  Notification)   │
                        └──────────────────┘
```

### Core Components Implementation

1. **API Layer**
   - RESTful endpoints following OpenAPI specification
   - Request validation using Pydantic models with custom validators
   - Authentication middleware (JWT verification for service-to-service, API key validation for clients)
   - Authorization middleware (RBAC enforcement with decorator and dependency injection)
   - Input sanitization (HTML escaping, SQL injection prevention)
   - Output encoding (JSON encoding, prevention of XSS in API responses)
   - Rate limiting (per IP, per API key, per user)
   - Request/response logging with correlation IDs
   - Exception handling with standardized error responses

2. **Application Layer**
   - Use cases: User lifecycle management, credential operations, preference management
   - Command/Query Responsibility Segregation (CQRS) for read-heavy operations
   - Transaction management for multi-step operations (user creation with profile setup)
   - Event publishing for state changes (using outsider pattern to avoid coupling)
   - Validation business rules (email uniqueness, password complexity, etc.)
   - Integration with external services (notification, authentication) via service clients
   - Background job handling for asynchronous operations (exports, imports, bulk operations)

3. **Domain Layer**
   - User aggregate root with encapsulated business logic
   - Value objects for email, phone number, authentication credentials
   - Domain events for internal communication (UserRegistered, PasswordChanged, etc.)
   - Specifications for complex validation rules (password strength, username availability)
   - Factories for creating user instances in different states (new, unverified, active, etc.)
   - Repositories for data access abstraction (UserRepository, CredentialRepository, etc.)

4. **Infrastructure Layer**
   - SQLAlchemy ORM models with defined relationships and constraints
   - Repository implementations with caching layers
   - Alembic migration scripts with data migration capabilities
   - Redis cache implementation with serialization strategies and fallback to DB
   - Encryption services for sensitive data (password hashes, API keys, MFA secrets)
   - Email/SMS service adapters (plugable architecture for different providers)
   - External service clients with circuit breaker, retry, and timeout policies
   - Background workers using RQ or Celery for asynchronous processing
   - Health check endpoints for liveness, readiness, and deep dependency checks

### Data Flow

#### User Registration Flow
1. Client submits POST `/api/v1/users` with user details (email, username, password, name)
2. API layer validates request structure and basic constraints (email format, password strength)
3. Application layer creates user use case:
   - Checks email and username uniqueness
   - Hashes password using bcrypt with configured cost
   - Generates verification tokens for email and/or phone
   - Creates user record in database (inactive, unverified)
   - Creates credential record with password hash
   - Creates empty preferences record
   - Sends verification email/SMS via notification service
   - Publishes `user.created.v1` event
4. Infrastructure persists data in atomic transaction
5. API returns user object (without sensitive data) with HTTP 201

#### Password Change Flow
1. Client posts to `/api/v1/users/{id}/password` with current and new password
2. API layer validates JWT and checks if user is self or admin
3. Application layer changes password use case:
   - Verifies current password against hash
   - Validates new password strength
   - Generates new password hash
   - Updates credential record with new hash and invalidates existing sessions (optional)
   - Logs security event
   - Publishes `user.password.changed.v1` event
4. Atomic database update
5. Returns success response

#### Token Validation Flow (Service-to-Service)
1. Service A calls User Service API with JWT in Authorization header
2. API layer extracts and validates JWT:
   - Checks signature with shared secret
   - Validates expiration and not-before times
   - Verifies required scopes/claims
3. If valid, proceeds with request; otherwise returns 401 Unauthorized
4. No database lookup typically needed for stateless JWT validation (unless token revocation is implemented)

#### Cross-Service Integration
- When Authentication Service publishes `auth.session.created.v1`:
  - User Service updates user's `last_login_at` timestamp
  - May update login attempt counters and lockout status
- When Organization Service publishes `organization.user.removed.v1`:
  - User Service may update user's organizational affiliations
  - If user belongs to no organizations, may trigger account review workflow
- When Notification Service publishes `notification.email.sent.v1`:
  - User Service updates verification attempt counters if applicable
  - Marks verification as completed if this was a verification email

## Running Tests

```bash
# Run unit tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_user.py
pytest tests/test_credential.py
pytest tests/test_profile.py
pytest tests/test_verification.py
@pytest.mark.integration
pytest -m integration

# Run security tests
pytest -m security

# Run performance tests
pytest -m performance
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database) with:
  - Automated backups
  - Point-in-time recovery
  - Read replicas for scaling read queries
  - Multi-AZ deployment for high availability
- Deploy Redis cluster for high availability and automatic failover
- Implement proper resource limits and requests in Kubernetes
- Enable pod disruption budgets for high availability
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault) for sensitive configuration
- Implement network policies to restrict traffic to only necessary services
- Enable mutual TLS (mTLS) between all services via service mesh
- Set up comprehensive monitoring and alerting:
  - API latency (p50, p95, p99)
  - Error rates (4xx, 5xx)
  - Database connection pool usage
  - Redis memory and connection metrics
  - Authentication failure rates
  - Account lockout events
  - Password reset request volumes
- Implement log aggregation and retention (ELK stack or similar)
- Schedule regular security scans and penetration tests
- Establish backup and disaster recovery procedures:
  - Hourly WAL archiving
  - Daily snapshots
  - Weekly full backups
  - Quarterly offsite backups
  - Annual restore drills

### Scaling Considerations
- Horizontally scale API instances behind load balancer (target <100ms p95 latency)
- Implement read replicas for PostgreSQL to distribute query load
- Use Redis clustering for cache scalability
- Consider partitioning users by ID hash or creation date for very large deployments (>10M users)
- Implement caching strategies for frequently accessed user profiles (e.g., frequently mentioned users in comments)
- Use CDN for serving user avatars and other static assets if applicable
- Implement batch processing for non-real-time operations:
  - Nightly user analytics aggregation
  - Weekly inactive account cleanup
  - Monthly data export requests

### Data Integrity & Consistency
- Use database transactions for operations that must be atomic (user creation with initial profile)
- Implement eventual consistency patterns for cross-domain events with idempotent handlers
- Use dead letter queues for failed event processing with manual retry capability
- Design event handlers to be idempotent to handle duplicate deliveries
- Implement data reconciliation jobs to detect and correct inconsistencies
- Use database constraints (unique indexes, foreign keys, check constraints) to prevent invalid states
- Implement application-level validation as a secondary line of defense
- Schedule regular data quality checks and cleanup jobs

## Maintenance

### Database Maintenance
```sql
-- Vacuum and analyze tables monthly
VACUUM ANALYZE users;
VACUUM ANALYZE user_credentials;
VACUUM ANALYZE user_preferences;
VACUUM ANALYZE user_sessions;
VACUUM ANALYZE user_verification;

-- Check for index bloat quarterly
SELECT schemaname, tablename, indexname, idx_bloat_ratio
FROM index_bloat
WHERE idx_bloat_ratio > 0.2;

-- Update statistics after large data modifications
ANALYZE;

-- Rebuild indexes annually or when bloat exceeds threshold
REINDEX TABLE users;
```

### Dependency Updates
```bash
# Check for outdated packages monthly
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U

# Update critical security patches immediately upon release
```

### Service Maintenance Tasks
- **Daily**:
  - Monitor authentication success/failure rates
  - Track account lockout events
  - Check for anomalous login patterns (impossible travel, new devices)
  - Monitor email/SMS delivery rates and bounce backs
  - Review failed payment attempts for users with paid features
- **Weekly**:
  - Review security logs for brute force attempts
  - Check for privilege escalation attempts
  - Validate backup integrity
  - Test password reset flow
  - Review API usage patterns for abnormal behavior
- **Monthly**:
  - Apply security patches to OS and dependencies
  - Test backup restore procedures
  - Review and update encryption keys
  - Conduct phishing simulation tests
  - Review third-party service integrations for changes
- **Quarterly**:
  - Conduct penetration testing
  - Review access logs for anomalous patterns
  - Evaluate database query performance and add indexes as needed
  - Test disaster recovery procedures
  - Review data retention and archiving policies
- **Annually**:
  - Comprehensive security audit and compliance verification (SOC 2, ISO 27001)
  - Update incident response plan
  - Update business continuity plan
  - Conduct tabletop exercises for security incidents
  - Review and update privacy policy and terms of service
  - Conduct user data export/delete request drills for GDPR/CCPA compliance

### Health Check Endpoints
- `GET /health` - Basic liveness check
- `GET /health/ready` - Readiness check (database connectivity, cache connectivity)
- `GET /health/live` - Liveness check (application responsiveness)
- `GET /health/detailed` - Comprehensive health including:
  - Database connection pool status and query latency
  - Redis connectivity, memory usage, and hit rate
  - Email/SMS provider connectivity and rate limit status
  - External service dependencies (Auth, Org, Team services)
  - Encryption key status and rotation schedule
  - Disk space and inode usage
  - File descriptor and thread pool usage
  - Background job queue depths