# Authentication Service

A secure authentication service for the QA Vision platform implementing email/password authentication, JWT-based session management with refresh token rotation, and foundational SSO integrations.

## Overview

This service provides core authentication and authorization functionality for the QA Vision platform. It implements industry-standard security practices including:
- Secure user registration and authentication with bcrypt password hashing
- JWT-based access tokens (configurable expiry, default 8 hours) 
- Refresh token rotation to prevent replay attacks
- Foundational SSO framework with Google ID token validation implemented
- Role-based access control with superuser privileges for administrative functions
- Pydantic-based request/response validation and OpenAPI documentation

## Current Implementation Status

### ✅ Fully Implemented Features
- **Email/Password Authentication**: User registration, login, logout with JWT tokens
- **Token Management**: Access tokens (8-hour expiry) and refresh tokens (30-day expiry) with automatic rotation
- **Password Reset Framework**: Endpoints present (require email/SMTP integration for production)
- **SSO Framework**: Google ID token validation fully implemented (GitHub/Azure placeholders for future implementation)
- **User Management**: Current user profile retrieval and update (self-service)
- **Administrative Functions**: Superuser-only endpoints for user listing and management
- **Security**: Bcrypt password hashing, JWT signing, token revocation, CORS protection
- **Testing**: Comprehensive unit and integration test suite
- **Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Deployment**: Dockerfile and docker-compose configuration

### 🔧 Framework Ready (Requires External Services)
- **Email/SMTP Integration**: Password reset endpoints implemented but require SMTP configuration
- **GitHub SSO**: Endpoint present but requires GitHub OAuth implementation
- **Azure AD SSO**: Endpoint present but requires Azure AD implementation
- **Account Lockout**: Framework present but requires configuration/enabling
- **HTTP-Only Cookies**: Ready for implementation if switching from bearer tokens to cookies

### 📝 Planned Enhancements
- Rate limiting on authentication endpoints
- Enhanced account lockout mechanisms
- Production-grade email templates for password reset
- Additional SSO providers (SAML, etc.)
- Multi-factor authentication (MFA) support
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
- `GITHUB_CLIENT_ID`: GitHub OAuth Client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth Client Secret
- `AZURE_TENANT_ID`: Azure AD Tenant ID
- `AZURE_CLIENT_ID`: Azure AD Client ID
- `AZURE_CLIENT_SECRET`: Azure AD Client Secret
- `SAML_SETTINGS`: SAML configuration (JSON object)

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user account
- `POST /api/v1/auth/login` - Login with email/password (returns access & refresh tokens)
- `POST /api/v1/auth/refresh-token` - Refresh access token using refresh token
- `POST /api/v1/auth/logout` - Logout by revoking refresh token
- `POST /api/v1/auth/forgot-password` - Initiate password reset (requires SMTP config)
- `POST /api/v1/auth/reset-password` - Complete password reset with token

### SSO Authentication
- `POST /api/v1/auth/sso/google` - Authenticate with Google ID token (IMPLEMENTED)
- `POST /api/v1/auth/sso/github` - Authenticate with GitHub (PLACEHOLDER - requires implementation)
- `POST /api/v1/auth/sso/azure` - Authenticate with Azure AD (PLACEHOLDER - requires implementation)

### User Management
- `GET /api/v1/auth/users/me` - Get current user's profile
- `PUT /api/v1/auth/users/me` - Update current user's profile
- `GET /api/v1/auth/users/` - List all users (SUPERUSER ONLY)
- `GET /api/v1/auth/users/{user_id}` - Get specific user by ID (SUPERUSER ONLY)

## Security Implementation Details

### Password Security
- Passwords hashed using bcrypt with work factor 12 via `passlib[bcrypt]`
- Never stored or transmitted in plain text
- Secure comparison using constant-time algorithms

### Token Management
- Access tokens: JWT signed with HMAC-SHA256, configurable expiration (default 8h)
- Refresh tokens: JWT signed with HMAC-SHA256, longer expiration (default 30d)
- Refresh token rotation: On each use, old token revoked and new token issued
- Token revocation: Server-side tracking enables immediate revocation on logout
- Optional Redis integration for token blacklisting/database synchronization

### Request Validation
- All input validated using Pydantic models
- Email format validation, password strength rules, length constraints
- Automatic 422 responses for malformed requests with detailed error messages

### SSO Security
- Google ID token validation using cryptographic signature verification
- Email domain validation to prevent account takeover attempts
- Account linking: SSO accounts can be linked to existing email/password users
- Just-in-time provisioning: New users created on first SSO login if email doesn't exist
- OAuth account linking prevents duplicate accounts for same user across providers

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