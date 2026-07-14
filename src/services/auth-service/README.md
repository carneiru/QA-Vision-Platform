# Authentication Service

This service provides authentication and authorization for the QA Vision platform, including:
- Email/password registration and login
- JWT-based session management
- Refresh token rotation
- SSO integration (Google, GitHub, Azure AD)
- Password reset and email verification
- User management APIs

## Features

- Secure password hashing using bcrypt
- JWT access tokens with refresh token rotation
- SSO support via OAuth 2.0 and SAML
- Rate limiting and brute force protection
- Session management and device tracking
- Multi-tenant support
- Comprehensive API documentation (OpenAPI/Swagger)
- Full test coverage

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL
- Docker and Docker Compose (optional)

### Installation

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in the required values
3. Install dependencies: `pip install -r requirements.txt`
4. Run database migrations: `alembic upgrade head`
5. Start the service: `python src/auth/main.py`

### Using Docker

```bash
docker-compose up --build
```

The service will be available at `http://localhost:8000`

## API Documentation

Once the service is running, visit:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

## Environment Variables

See `.env.example` for all required and optional configuration options.

## Testing

Run the test suite with:
```bash
pytest
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with email/password
- `POST /api/v1/auth/refresh-token` - Refresh access token
- `POST /api/v1/auth/logout` - Logout by revoking refresh token
- `POST /api/v1/auth/forgot-password` - Initiate password reset
- `POST /api/v1/auth/reset-password` - Confirm password reset

### SSO Authentication
- `POST /api/v1/auth/sso/google` - Login with Google
- `POST /api/v1/auth/sso/github` - Login with GitHub
- `POST /api/v1/auth/sso/azure` - Login with Azure AD

### User Management
- `GET /api/v1/auth/users/` - List users (admin only)
- `GET /api/v1/auth/users/me` - Get current user
- `PUT /api/v1/auth/users/me` - Update current user
- `GET /api/v1/auth/users/{user_id}` - Get user by ID (admin only)

## Security Features

- Passwords hashed with bcrypt (work factor 12)
- JWT tokens signed with HS256
- Refresh token rotation to prevent replay attacks
- Account lockout after failed attempts (configurable)
- Secure HTTP-only cookies for token storage (when implemented)
- CORS protection
- SQL injection prevention via ORM
- Input validation via Pydantic

## License

MIT
