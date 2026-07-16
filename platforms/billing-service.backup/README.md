# Billing/Subscription Service

A comprehensive billing and subscription management service for the QA Vision platform handling subscriptions, billing, invoicing, and payment processing.

## Overview

This service provides comprehensive billing and subscription management functionality for the QA Vision platform. It handles customer subscriptions, recurring billing, invoice generation, payment processing, and integration with payment gateways like Stripe and PayPal.

## Features

### ✅ Implemented
- **Subscription Management**: Create, retrieve, update, cancel, renew, pause, and resume subscriptions
- **Invoice Management**: Generate, retrieve, and pay invoices
- **Payment Method Management**: Add, retrieve, and remove payment methods
- **Payment Gateway Integration**: Stripe and PayPal integration (webhooks and direct API)
- **Billing Portal**: Customer self-service portal for managing subscriptions and payments
- **Webhook Handling**: Secure webhook endpoints for payment gateway events
- **Multi-tenancy**: Tenant-aware billing context for SaaS deployments
- **Privatable API**: Secure API endpoints with authentication and authorization
- **Database Persistence**: PostgreSQL storage for subscriptions, invoices, and payment methods
- **Caching Layer**: Redis integration for pricing and plan information caching
- **Event Publishing**: Domain events for integration with other services
- **Comprehensive Testing**: Unit and integration tests for all functionality
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 🔧 Configuration Required
- **Payment Gateway Accounts**: Stripe and/or PayPal merchant accounts
- **Email/SMTP Configuration**: For invoice and receipt emails
- **Price Configuration**: Product and pricing setup in payment gateways
- **Tax Configuration**: Tax rates and rules (if applicable)

### 📝 Planned Enhancements
- Tax calculation and VAT/GST support
- Multiple currency support
- Advanced invoicing (custom line items, tax-inclusive/exclusive pricing)
- Revenue recognition reporting
- Dunning management for failed payments
- Subscription metering and usage-based billing
- Advanced analytics and revenue forecasting
- Additional payment gateways (Adyen, Braintree, etc.)

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis 6.0+ (optional, for caching)
- Stripe and/or PayPal merchant accounts
- (Optional) Docker and Docker Compose

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd qa-ai-dashboard/platforms/billing-service/billing-service
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

5. **Configure payment gateways**
   - Set up Stripe account and obtain API keys
   - Set up PayPal account and obtain API credentials
   - Configure webhooks in both platforms to point to your service

6. **Run the application**
   ```bash
   # Development mode
   python src/billing/main.py
   
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
- `APP_NAME`: Service name (default: "Billing Service")
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
- `POSTGRES_SERVER`: Database host (default: "localhost")
- `POSTGRES_USER`: Database username (default: "postgres")
- `POSTGRES_PASSWORD`: Database password (default: "postgres")
- `POSTGRES_DB`: Database name (default: "billing_db")
- **OR** `DATABASE_URL`: Full connection string (overrides individual POSTGRES_* vars)

### Redis Configuration (Optional - for caching)
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password (if required)

### Payment Gateway Configuration
#### Stripe
- `STRIPE_SECRET_KEY`: Stripe secret key
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret for signature verification
- `STRIPE_PUBLISHABLE_KEY`: Stripe publishable key (for client-side if needed)

#### PayPal
- `PAYPAL_CLIENT_ID`: PayPal client ID
- `PAYPAL_CLIENT_SECRET`: PayPal client secret
- `PAYPAL_MODE`: `sandbox` or `live`

### SMTP Configuration (For Invoice and Receipt Emails)
- `SMTP_TLS`: Enable TLS (default: True)
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_HOST`: SMTP hostname
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAILS_FROM_EMAIL`: Sender email address
- `EMAILS_FROM_NAME`: Sender name

### Price and Plan Configuration
- `PRICE_CACHE_TTL_SECONDS`: How long to cache pricing information (default: 3600 = 1 hour)
- `DEFAULT_CURRENCY`: Default currency for pricing (default: "usd")

### CORS Configuration
- `BACKEND_CORS_ORIGINS`: List of allowed origins (default: ["http://localhost:3000", "http://localhost:8000"])

## API Endpoints

### Subscription Management
- `POST   /api/v1/subscriptions`                     # Create new subscription
- `GET    /api/v1/subscriptions`                     # List subscriptions (with filtering and pagination)
- `GET    /api/v1/subscriptions/{id}`                # Get subscription by ID
- `PUT    /api/v1/subscriptions/{id}`                # Update subscription
- `DELETE /api/v1/subscriptions/{id}`                # Cancel subscription
- `POST   /api/v1/subscriptions/{id}/renew`          # Renew subscription
- `POST   /api/v1/subscriptions/{id}/pause`          # Pause subscription
- `POST   /api/v1/subscriptions/{id}/resume`         # Resume subscription

### Invoice Management
- `GET    /api/v1/invoices`                          # List invoices (with filtering and pagination)
- `GET    /api/v1/invoices/{id}`                     # Get invoice by ID
- `POST   /api/v1/invoices/{id}/pay`                 # Process payment for invoice

### Payment Methods
- `GET    /api/v1/payment-methods`                   # List payment methods
- `POST   /api/v1/payment-methods`                   # Add payment method
- `DELETE /api/v1/payment-methods/{id}`              # Remove payment method

### Webhooks
- `POST   /api/v1/webhooks/stripe`                   # Stripe webhook endpoint
- `POST   /api/v1/webhooks/paypal`                   # PayPal webhook endpoint

### Customer Portal
- `GET    /api/v1/billing-portal`                    # Get customer portal URL

## Request/Response Models

### Subscription
- **Request**: `SubscriptionCreate` (plan_id, quantity, trial_period_days, coupon_id)
- **Response**: `Subscription` (id, plan_id, customer_id, status, current_period_start, current_period_end, trial_start, trial_end, cancel_at_period_end, created_at, updated_at, organization_id)

### Invoice
- **Response**: `Invoice` (id, number, amount, currency, status, due_date, paid_at, period_start, period_end, subscription_id, created_at)

### Payment Method
- **Request**: `PaymentMethodCreate` (type, token [for Stripe/PayPal tokens] or card details)
- **Response**: `PaymentMethod` (id, customer_id, type, brand, last4, exp_month, exp_year, is_default)

### Webhook Responses
- Return appropriate HTTP status codes (200 for success, 4xx for client errors, 5xx for server errors)
- Log all webhook events for auditing and troubleshooting

## Dependencies

- **Authentication Service**: For user validation and tenant context
- **Organization Service**: For organization/billing context and customer mapping
- **Payment Gateway**: Stripe and/or PayPal APIs for payment processing
- **Redis**: Caching layer for pricing plans and frequently accessed data
- **PostgreSQL**: Persistent storage for subscriptions, invoices, payment types, and billing relationships
- **Email Service**: SMTP for sending invoices, receipts, and billing notifications

## Event Contracts

### Events Published
- `subscription.created.v1` - When a new subscription is created
- `subscription.updated.v1` - When a subscription is updated (plan change, quantity change, etc.)
- `subscription.canceled.v1` - When a subscription is canceled
- `subscription.renewed.v1` - When a subscription is renewed
- `subscription.paused.v1` - When a subscription is paused
- `subscription.resumed.v1` - When a subscription is resumed
- `invoice.created.v1` - When an invoice is generated
- `invoice.paid.v1` - When an invoice is successfully paid
- `invoice.failed.v1` - When an invoice payment fails
- `payment.method.added.v1` - When a new payment method is added
- `payment.method.removed.v1` - When a payment method is removed
- `payment.charge.failed.v1` - When a payment charge fails
- `payment.charge.succeeded.v1` - When a payment charge succeeds

### Events Consumed
- `customer.created.v1` - From Authentication/Organization service when new customer is created
- `customer.updated.v1` - From Authentication/Organization service when customer data changes
- `customer.deleted.v1` - From Authentication/Organization service when customer is deleted
- `subscription.plan.changed.v1` - From catalog/service when pricing or plans change

## Database Schema

### Subscriptions Table
- `id`: UUID (Primary Key)
- `plan_id`: String (Reference to pricing plan)
- `customer_id`: UUID (Links to customer in auth/org service)
- `organization_id`: UUID (For multi-tenancy)
- `status`: Enum (active, canceled, past_due, unpaid, incomplete, trialing, paused)
- `current_period_start`: Timestamp
- `current_period_end`: Timestamp
- `trial_start`: Timestamp (nullable)
- `trial_end`: Timestamp (nullable)
- `cancel_at_period_end`: Boolean
- `created_at`: Timestamp
- `updated_at`: Timestamp

### Invoices Table
- `id`: UUID (Primary Key)
- `number`: String (Unique invoice number)
- `amount`: Decimal
- `currency`: String (ISO 4217 currency code)
- `status`: Enum (draft, open, paid, void, uncollectible)
- `due_date`: Timestamp
- `paid_at`: Timestamp (nullable)
- `period_start`: Timestamp
- `period_end`: Timestamp
- `subscription_id`: UUID (Foreign Key)
- `created_at`: Timestamp
- `updated_at`: Timestamp

### Payment Methods Table
- `id`: UUID (Primary Key)
- `customer_id`: UUID (Foreign Key)
- `type`: Enum (card, bank_account, paypal, etc.)
- `provider`: String (stripe, paypal, etc.)
- `provider_id`: String (ID in payment gateway)
- `last4`: String (last 4 digits for card)
- `brand`: String (visa, mastercard, etc. for card)
- `exp_month`: Integer (for card)
- `exp_year`: Integer (for card)
- `is_default`: Boolean
- `created_at`: Timestamp
- `updated_at`: Timestamp

## Security Implementation

### Authentication & Authorization
- JWT-based authentication with refresh token rotation
- Role-based access control (admin, accountant, viewer)
- Tenant isolation ensuring customers can only access their own billing data
- API key authentication for webhook endpoints from payment gateways

### Data Protection
- PCI DSS compliance for payment data handling
- Sensitive data encryption at rest (payment tokens, etc.)
- TLS encryption for all data in transit
- Secure webhook signature verification
- No storage of full credit card numbers (only last 4 digits and token)

### Rate Limiting & Abuse Protection
- Rate limiting on public endpoints (webhooks exempt)
- IP-based threat detection and blocking
- Payment attempt velocity limits
- Account lockout after excessive failed payment attempts

## Payment Gateway Integration

### Stripe Integration
- Uses Stripe Billing for subscription management
- Webhooks for asynchronous event handling
- Payment Intents API for secure payment processing
- Customer portal integration for self-service
- Automatic tax calculation via Stripe Tax (when enabled)

### PayPal Integration
- PayPal Orders API for one-time payments
- PayPal Subscriptions API for recurring payments
- Webhook handling for event notifications
- Reference transactions for seamless payment method updates

## Implementation Details

### Technology Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Caching**: Redis (optional)
- **Payment Gateways**: Stripe Python SDK, PayPal Python SDK
- **API Documentation**: OpenAPI 3.0 with Swagger UI
- **Testing**: Pytest with coverage reporting
- **Containerization**: Docker and Docker Compose

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ API Layer       │    │ Business Logic   │    │ Data Access      │
│ (REST Endpoints)│    │ (Subscription    │    │ (Repository)     │
└─────────────────┘    │  Management,     │    └──────────────────┘
                       │  Invoice Gen,    │    ┌──────────────────┐
                       │  Payment Proc)   │    │ External Services│
┌─────────────────┐    │                  │    │ (Stripe, PayPal) │
│ Webhook Handlers│    └──────────────────┘    └──────────────────┘
└─────────────────┘
```

## Running Tests

```bash
# From the billing-service directory
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test suites
pytest tests/test_subscription_service.py
pytest tests/test_invoice_service.py
pytest tests/test_payment_service.py
```

## Deployment Considerations

### Production Environment
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Use managed Redis (AWS ElastiCache, Redis Cloud, etc.)
- Terminate SSL at load balancer or ingress controller
- Use secrets manager for API keys and credentials (AWS Secrets Manager, HashiCorp Vault)
- Implement proper logging and monitoring (ELK stack, Datadog, etc.)
- Set up automated backups for PostgreSQL
- Configure audit logging for financial transactions

### Scaling Considerations
- Stateless API servers behind load balancer
- Read replicas for database reporting queries
- Redis clustering for high availability
- Circuit breaker pattern for payment gateway calls
- Async processing for invoice generation and email sending
- CDN for serving billing portal assets

### Compliance & Security
- PCI DSS SAQ EP compliance (outsourced card processing)
- GDPR/CCPA data protection for customer information
- SOC 2 Type II compliance controls
- Regular security scanning and penetration testing
- Audit trail for all financial transactions
- Data retention policies for financial records

## Troubleshooting

### Common Issues

**Payment Gateway Connection Errors**
- Verify API keys are correct and not expired
- Check webhook URLs are correctly configured in gateway dashboards
- Ensure server is accessible from payment gateway IPs (for webhooks)
- Validate API permissions and account status

**Database Connection Errors**
- Verify PostgreSQL is running and accessible
- Check connection string and credentials
- Ensure database exists and user has sufficient privileges
- Verify network connectivity and firewall rules

**Webhook Signature Verification Failures**
- Confirm webhook secret matches what's configured in gateway
- Ensure webhook endpoint is receiving the raw request body
- Check for proxy or middleware that might alter the request
- Validate timestamp tolerance settings

**Invoice Generation Issues**
- Verify subscription has valid plan and pricing
- Check date calculations for billing periods
- Ensure tax configuration is correct (if enabled)
- Verify currency conversion rates (if multi-currency)

### Log Analysis
- Application logs startup configuration and connection status
- Payment attempts logged at INFO level (no sensitive data)
- Webhook receipts and processing logged for audit trail
- Database connection errors logged with context
- Integration points with auth/org services logged for troubleshooting

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

### Backup Procedures
- **Database**: Automated daily snapshots with point-in-time recovery
- **Configuration**: Version-controlled environment templates
- **Secrets**: Regular rotation of API keys and credentials
- **Logs**: Centralized logging with retention policies

## Product Considerations

### Pricing Models Supported
- Flat-rate subscriptions
- Tiered pricing (volume-based)
- Per-unit pricing
- Overage billing
- Trial periods
- Coupons and discounts
- Proration on plan changes

### Payment Methods Supported
- Credit/Debit Cards (Visa, Mastercard, American Express, Discover)
- Bank Transfers (ACH, SEPA)
- Digital Wallets (Apple Pay, Google Pay via Stripe)
- PayPal
- Local payment methods (via Stripe/PayPal expansion)

### Billing Features
- Prorate adjustments for plan changes
- Trial period management
- Coupon and discount code support
- Tax calculation and reporting
- Multi-currency support (planned)
- Invoice customization and branding
- Automatic retry logic for failed payments
- Subscription lifecycle management
- Renewal automation
- Grace period and suspension handling

## Future Roadmap

### Phase 1: Core Billing (Complete)
- Basic subscription management
- Invoice generation and payment processing
- Payment method storage
- Basic webhook handling

### Phase 2: Enhanced Features
- Tax calculation and reporting
- Multi-currency support
- Advanced invoicing templates
- Revenue recognition reporting
- Dunning management

### Phase 3: Advanced Capabilities
- Usage-based billing
- Contract management
- Advanced analytics and forecasting
- Customer revenue attribution
- Automated compliance reporting

---
*This service implements industry-standard billing practices and integrates with leading payment gateways to provide secure, reliable, and scalable billing functionality for the QA Vision platform.*
