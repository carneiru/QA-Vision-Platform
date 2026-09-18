# QA Vision Platform

A comprehensive quality assurance and analytics platform with AI-powered test analysis capabilities.

## Overview

QA Vision is a microservices-based platform designed to provide end-to-end quality assurance workflow management, test analytics, and AI-driven insights. The platform consists of several independent services that communicate via well-defined APIs.

## Current Implementation: Authentication Service (Phase 1)

The first phase of the platform implements a robust authentication service with the following features:

### Features
- **Email/Password Authentication** - Secure user registration and login with bcrypt password hashing
- **Token Management** - JWT access tokens (default 60 minutes) and opaque refresh tokens stored in the database (30 days), rotated on use with replay detection
- **Refresh Token Rotation** - The presented refresh token is revoked and replaced on each use
- **Google SSO** - ID tokens verified against Google's JWKS. GitHub and Azure AD return 501; they were previously mocks that accepted any input.
- **Role-Based Access Control** - Superuser-only endpoints for user listing
- **Multi-tenancy Support** - The user model carries a nullable `tenant_id`; authoritative membership lives in organization-service
- **API** - RESTful endpoints with auto-generated OpenAPI documentation
- **Tests** - 30 unit and integration tests covering authentication, SSO verification and cross-user isolation
- **Dockerized Deployment** - Docker Compose setup with PostgreSQL

### Technology Stack
- **Language**: Python 3.9
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Authentication**: PyJWT (including `PyJWKClient` for Google's signing keys), passlib[bcrypt]
- **SSO**: Google ID token verification via PyJWT. Authlib and python-jose are in `requirements.txt` but unused.
- **Validation**: Pydantic
- **Containerization**: Docker & Docker Compose
- **Testing**: Pytest

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL
- Docker and Docker Compose (optional but recommended)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd QA-Vision-Platform
   ```

2. **Environment Configuration**
   ```bash
   cp platforms/auth-service/auth-service/.env.example platforms/auth-service/auth-service/.env
   # Edit .env with your configuration values
   ```

3. **Install Dependencies (Development)**
   ```bash
   cd platforms/auth-service/auth-service
   pip install -r requirements.txt
   ```

4. **Database Setup**
   ```bash
   # Apply migrations
   alembic upgrade head
   ```

5. **Run the Service**
   ```bash
   # Development mode
   python src/auth/main.py
   
   # Or using Docker Compose
   docker-compose up --build
   ```

### Environment Variables

The application uses environment variables for configuration. Copy the `.env.example` file to `.env` and adjust the values as needed.

The `.env.example` file contains the following variables:

- **Application**: `APP_NAME`, `APP_VERSION`, `DEBUG`
- **API**: `API_V1_STR`
- **Security**: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ALGORITHM`
- **Database**: `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (or `DATABASE_URL` for direct connection string)
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` (optional, for token blacklisting)
- **SMTP**: `SMTP_TLS`, `SMTP_PORT`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME` (for email notifications)
- **SSO Providers**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `SAML_SETTINGS`
- **CORS**: `BACKEND_CORS_ORIGINS` (list of allowed origins)

### API Documentation

Once the service is running, visit:
- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`

### Running Tests
```bash
# From the auth service directory
pytest
```

## Project Structure

Services are grouped by domain at the repository root. Only the two under
`platforms/` are implemented; the other domain directories hold scaffolding
generated from the auth-service template and are not running services yet.

```
QA-Vision-Platform/
├── platforms/
│   ├── auth-service/auth-service/  # Authentication (implemented)
│   │   ├── src/auth/
│   │   │   ├── api/                # FastAPI endpoints
│   │   │   ├── db/                 # Session and declarative base
│   │   │   ├── models/             # SQLAlchemy models
│   │   │   ├── schemas/            # Pydantic validation models
│   │   │   ├── service/            # Business logic layer
│   │   │   ├── utils/              # Password and token helpers
│   │   │   └── config.py           # Settings
│   │   ├── tests/                  # Test suite
│   │   ├── alembic/                # Database migrations
│   │   └── requirements.txt
│   └── organization-service/       # Organizations, members, invitations (implemented)
├── intelligence/                   # Planned: AI analysis services
├── execution/                      # Planned: test execution services
├── integrations/                   # Planned: third-party connectors
├── collaboration/                  # Planned
├── administration/                 # Planned
├── automation/                     # Planned
├── marketplace/                    # Planned
└── docs/                           # Architecture, specs and implementation plans
```

## Security Features
- Passwords hashed with bcrypt
- Access tokens signed with HS256; refresh tokens are opaque and revocable server-side
- Refresh token rotation on every use, with expiry enforced at verification
- Google ID tokens verified by signature, audience, issuer, expiry and verified-email claim
- SQL injection prevention via the ORM
- Input validation via Pydantic models
- CORS configuration
- Environment-based configuration (no hardcoded secrets)

Not present, despite earlier claims here: brute-force protection or account
lockout (no failed-attempt tracking exists), Redis token blacklisting (the URL
is configurable and unused), and password reset (both endpoints return 501).
Access tokens are not revocable — logging out revokes the refresh token, but an
already-issued access token remains valid until it expires.

## Future Phases

The QA Vision platform is planned to be implemented in multiple phases:

1. **Phase 1: Foundation Services** (Current) - Auth, Organization, Project services
2. **Phase 2: Test Management** - Test case management, execution tracking
3. **Phase 3: Defect Tracking** - Bug reporting and management
4. **Phase 4: Test Execution** - Test runner integrations and scheduling
5. **Phase 5: Analytics & Reporting** - Dashboards, metrics, trend analysis
6. **Phase 6: AI Engine** - Predictive analytics, test optimization, failure analysis

## License

MIT License - see LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## Support

For questions and support, please open an issue in the repository.