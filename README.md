# QA Vision Platform

A comprehensive quality assurance and analytics platform with AI-powered test analysis capabilities.

## Overview

QA Vision is a microservices-based platform designed to provide end-to-end quality assurance workflow management, test analytics, and AI-driven insights. The platform consists of several independent services that communicate via well-defined APIs.

## Current Implementation: Authentication Service (Phase 1)

The first phase of the platform implements a robust authentication service with the following features:

### Features
- **Email/Password Authentication** - Secure user registration and login with bcrypt password hashing
- **JWT Token Management** - Access tokens (8-day expiry) and refresh tokens (30-day expiry) for stateless authentication
- **Refresh Token Rotation** - Automatic rotation to prevent replay attacks
- **SSO Framework** - Plug-and-play support for Google, GitHub, and Azure AD (placeholders implemented)
- **Role-Based Access Control** - Admin-only endpoints for user management
- **Multi-tenancy Support** - Tenant-aware user model for SaaS deployments
- **Comprehensive API** - RESTful endpoints with OpenAPI 3.3.3.0 documentation
- **Full Test Coverage** - Unit and integration tests for all critical functionality
- **Dockerized Deployment** - Easy setup with PostgreSQL database

### Technology Stack
- **Language**: Python 3.9
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Authentication**: PyJWT, python-jose, passlib[bcrypt]
- **SSO**: Authlib (framework ready)
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
   cp src/services/auth-service/.env.example src/services/auth-service/.env
   # Edit .env with your configuration values
   ```

3. **Install Dependencies (Development)**
   ```bash
   cd src/services/auth-service
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

```
QA-Vision-Platform/
├── src/
│   └── services/
│       └── auth-service/           # Authentication Service (Phase 1)
│           ├── src/
│           │   └── auth/           # Python package
│           │       ├── api/        # FastAPI endpoints
│           │       ├── core/       # Configuration
│           │       ├── db/         # Database models & session
│           │       ├── models/     # SQLAlchemy models
│           │       ├── schemas/    # Pydantic validation models
│           │       ├── service/    # Business logic layer
│           │       └── utils/      # Security utilities (password, tokens)
│           ├── tests/              # Test suite
│           ├── alembic/            # Database migrations
│           ├── Dockerfile
│           ├── docker-compose.yml
│           ├── requirements.txt
│           ├── .env.example        # Example environment file
│           └── .gitignore
├── docs/                           # Architecture and design documents
├── ai-engine/                      # Future AI Engine service (Phase 6)
└── TODO.md                         # Implementation progress tracking
```

## Security Features
- Passwords hashed with bcrypt (work factor 12)
- JWT tokens signed with HS256 algorithm
- Automatic refresh token rotation
- Account protection against brute force (configurable)
- SQL injection prevention via ORM
- Input validation via Pydantic models
- CORS protection
- Environment-based configuration (no hardcoded secrets)

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