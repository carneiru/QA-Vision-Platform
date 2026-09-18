# Authentication Service

Authentication for the QA Vision platform: email/password accounts, JWT access tokens with revocable database-backed refresh tokens, and Google SSO.

## Overview

This service provides core authentication and authorization functionality for the QA Vision platform. It implements industry-standard security practices including:
- Secure user registration and authentication with bcrypt password hashing
- JWT access tokens (configurable expiry, default 8 hours)
- Opaque refresh tokens stored server-side, rotated on use and revocable on logout
- Google SSO with full ID token verification against Google's JWKS
- Role-based access control with superuser privileges for administrative functions
- Pydantic-based request/response validation and OpenAPI documentation

## Current Implementation Status

### ✅ Implemented and tested
- **Email/Password Authentication**: registration, login, logout
- **Token Management**: JWT access tokens (8-hour expiry) and opaque database-backed refresh tokens (30-day expiry) with rotation on use and server-side revocation
- **Google SSO**: ID tokens verified against Google's JWKS (RS256 signature, audience, issuer, expiry, verified email)
- **User Management**: self-service profile read and update, restricted to non-privileged fields
- **Administrative Functions**: superuser-only user listing
- **Security**: bcrypt password hashing, CORS configuration, cross-user isolation on every identity-resolving path
- **Testing**: 30 unit and integration tests, including the SSO verification path against a locally generated signing key
- **Documentation**: auto-generated OpenAPI/Swagger
- **Deployment**: Dockerfile and docker-compose configuration

### ⛔ Not implemented — these endpoints return 501
- **Password Reset** (`/forgot-password`, `/reset-password`): no reset-token model, no mail transport. Both previously returned success without doing anything.
- **GitHub SSO**: requires an OAuth code exchange that does not exist
- **Azure AD SSO**: requires an Azure AD code exchange that does not exist

### 📝 Not built
- **Linking Google to an existing password account**: refused with 409. Doing it safely needs an authenticated link endpoint; see SSO Security below.
- **Account lockout**: no failed-attempt tracking exists anywhere in this service
- **Redis token blacklisting**: a Redis URL is configurable, but nothing reads it
- **HTTP-only cookie sessions**: bearer tokens only
- Rate limiting on authentication endpoints
- Additional SSO providers (SAML, etc.)
- Multi-factor authentication (MFA)
- Advanced session management (device tracking, concurrent session limits)

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/src/services/auth-service
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
   # Ensure PostgreSQL is running and create the database if needed
   # Then apply migrations
   alembic upgrade head
   ```

5. **Run the application**
   ```bash
   # Development mode
   python src/auth/main.py
   
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
- `APP_NAME`: Service name (default: "Auth Service")
- `APP_VERSION`: Version identifier (default: "0.1.0")
- `DEBUG`: Enable debug mode (default: False)

### API Configuration
- `API_V1_STR`: API version prefix (default: "/api/v1")

### Security Settings
- `SECRET_KEY`: Secret key for JWT signing (REQUIRED - change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime in minutes (default: 480 = 8 hours)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token lifetime in days (default: 30)
- `ALGORITHM`: JWT signing algorithm (default: "HS256")

### Database Connection
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "auth_db")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Redis Configuration (Optional - for token blacklisting)
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)

### SMTP Configuration (For Password Reset Emails)
- `SMTP_TLS`: Enable TLS (default: True)
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_HOST`: SMTP hostname
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAILS_FROM_EMAIL`: Sender email address
- `EMAILS_FROM_NAME`: Sender name

### SSO Provider Configuration
- `GOOGLE_CLIENT_ID`: Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth Client Secret

The settings below are accepted by the config module but nothing reads them yet — the
providers they configure return 501:
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
- `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- `SAML_SETTINGS`

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user account
- `POST /api/v1/auth/login` - Login with email/password (returns access & refresh tokens)
- `POST /api/v1/auth/refresh-token` - Refresh access token using refresh token
- `POST /api/v1/auth/logout` - Logout by revoking refresh token
- `POST /api/v1/auth/forgot-password` - **501, not implemented**
- `POST /api/v1/auth/reset-password` - **501, not implemented**

### SSO Authentication
- `POST /api/v1/sso/google` - Authenticate with a Google ID token
- `POST /api/v1/sso/github` - **501, not implemented**
- `POST /api/v1/sso/azure` - **501, not implemented**

### User Management
- `GET /api/v1/users/me` - Get current user's profile
- `PUT /api/v1/users/me` - Update current user's profile. Accepts `UserSelfUpdate` only: email, password, full_name, avatar_url, department, job_title. `is_active` and `is_superuser` are not settable here.
- `GET /api/v1/users/` - List all users (SUPERUSER ONLY)
- `GET /api/v1/users/{user_id}` - Get a user by id (own account, or any account for a superuser)

There is no endpoint that grants superuser. The flag is set directly in the database.

## Security Implementation Details

### Password Security
- Passwords hashed using bcrypt with work factor 12 via `passlib[bcrypt]`
- Never stored or transmitted in plain text
- Secure comparison using constant-time algorithms

### Token Management
- Access tokens: JWT signed with HMAC-SHA256, configurable expiration (default 8h)
- Refresh tokens: opaque 32-byte random strings (`secrets.token_urlsafe`) stored in `refresh_tokens`, default 30d. They are not JWTs — being database rows is what makes revocation immediate and rotation meaningful.
- Refresh token rotation: on each use the presented token is revoked and a new one issued
- Expiry is enforced on verification, not only at issuance
- Logout revokes only a token belonging to the caller, so knowing someone else's token value does not let you end their session

### Request Validation
- All input validated using Pydantic models
- Email format validation, password strength rules, length constraints
- Automatic 422 responses for malformed requests with detailed error messages

### SSO Security
- Google ID tokens are verified against Google's published JWKS: RS256 signature, `aud` matching `GOOGLE_CLIENT_ID`, issuer in Google's set, `exp`, and `email_verified` being boolean `true`
- With no `GOOGLE_CLIENT_ID` configured the endpoint returns 503 rather than verifying without an audience, which would accept ID tokens minted for any other Google application
- Just-in-time provisioning: a first-time Google user is created with no password
- **Account linking is restricted.** A verified Google email proves control of the mailbox, not ownership of a local account sharing that address. Google is auto-linked only to a passwordless row. An account that has a password returns 409, as does an account already linked to a different Google `sub`. Linking Google to an existing password account requires an authenticated link endpoint, which is not built.

### Administrative Controls
- Superuser-only endpoints protected by role-based checks
- Sensitive operations (user listing, admin lookups) restricted to privileged accounts
- Regular users can only access their own data

## Project Structure

```
src/
└── auth/                    # Main Python package
    ├── api/                 # FastAPI route handlers
    │   ├── v1/              # API version 1
    │   │   ├── endpoints/   # Route definitions
    │   │   │   ├── auth.py      # Authentication endpoints
    │   │   │   ├── users.py     # User management endpoints
    │   │   │   └── sso.py       # SSO authentication endpoints
    │   │   └── deps.py        # Dependency injection (DB, auth)
    │   └── main.py          # Application entry point
    ├── core/                # Core configuration and settings
    │   └── config.py        # Pydantic settings management
    ├── db/                  # Database layer
    │   ├── session.py       # Database session management
    │   └── models/          # SQLAlchemy models
    ├── models/              # Pydantic and SQLAlchemy models
    │   ├── user.py          # User model and related entities
    │   └── oauth.py         # OAuth account linking model
    ├── schemas/             # Pydantic validation schemas
    │   ├── auth.py          # Authentication request/response models
    │   └── user.py          # User request/response models
    ├── service/             # Business logic layer
    │   ├── user_service.py  # User CRUD and authentication logic
    │   ├── auth_service.py  # Token creation, validation, refresh logic
    │   └── sso_service.py   # SSO token validation and processing
    ├── utils/               # Utility functions
    │   ├── password.py      # Bcrypt password hashing/verification
    │   ├── tokens.py        # JWT token creation and validation
    │   └── dependencies.py  # FastAPI dependencies (auth, DB)
    └── tests/               # Test suite
        ├── conftest.py      # Pytest fixtures and configuration
        ├── test_*py         # Unit and integration tests
```

## Running Tests

```bash
# From the auth-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test files
pytest tests/test_auth_endpoints.py
pytest tests/test_user_service.py
```

## Docker Deployment

### Development
```bash
docker-compose up --build
```

### Production
```bash
# Build image
docker build -t qtauth-service .

# Run container
docker run -p 8000:8000 \
  --env-file .env.prod \
  qtauth-service
```

### docker-compose.yml Services
- `app`: FastAPI application server
- `db`: PostgreSQL database
- `redis`: Redis instance (optional, for token blacklisting)

## Production Considerations

### Environment Security
- **SECRET_KEY**: Must be strong and kept secret (use secrets manager in production)
- **Database Credentials**: Use managed secrets or environment-specific configuration
- **SSO Credentials**: Store provider secrets securely (never commit to version control)

### Performance & Scaling
- Database connection pooling configured via SQLAlchemy
- Stateless API design enables horizontal scaling behind load balancer
- Redis recommended for token blacklisting in multi-instance deployments
- Consider CDN for serving OpenAPI documentation in production

### Monitoring & Observability
- Structured logging recommended for production deployment
- Health check endpoint available at `/health` (add via middleware if needed)
- Consider integrating with APM (Application Performance Monitoring) tools
- Audit logging for security-sensitive operations (login attempts, privilege changes)

### Backup & Recovery
- Regular database backups recommended
- Point-in-time recovery capability depends on PostgreSQL configuration
- Test backup and restore procedures regularly

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

## Troubleshooting

### Common Issues

**Database Connection Errors**
- Verify PostgreSQL is running and accessible
- Check `POSTGRES_*` environment variables or `DATABASE_URL`
- Ensure database exists and user has correct permissions

**Authentication Failures**
- Verify `SECRET_KEY` is consistent across all instances (if scaled)
- Check token expiration settings
- Ensure bcrypt is properly installed (`pip install passlib[bcrypt]`)

**SSO Authentication Issues**
- Verify Google Client ID/Secret are correctly configured
- Check system clock synchronization (token validation is time-sensitive)
- Review OAuth consent screen configuration in Google Cloud Console

**Email/Password Reset Issues**
- Verify SMTP server connectivity and credentials
- Check `EMAILS_FROM_EMAIL` and `EMAILS_FROM_NAME` settings
- Test email delivery independently of application

### Log Analysis
- Application logs startup configuration and connection status
- Authentication attempts logged at INFO level (no credentials, password hashing, user creation, and token operations)
- Clean interfaces for token generation and validation
- Integrates with user service for data persistence and uses secure password handling via bcrypt

Usage: The auth service is called by API endpoints to handle user registration, login, password reset, and session management. It ensures secure credential storage and verification while providing clean interfaces for token generation and validation.