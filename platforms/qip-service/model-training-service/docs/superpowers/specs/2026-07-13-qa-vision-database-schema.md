# QA Vision Platform Database Schema Design

## Overview
This document details the PostgreSQL database schema for the QA Vision platform, designed to support enterprise-scale quality intelligence operations following Domain-Driven Design principles.

## Design Principles
- **Normalization**: 3NF where beneficial, denormalization for performance where needed
- **Multi-tenancy**: Organization-based isolation with proper indexing
- **Auditability**: Complete audit trail for all entities
- **Performance**: Strategic indexing, partitioning, and materialized views
- **Extensibility**: Flexible schema for custom attributes and plugin data
- **Data Integrity**: Foreign key constraints, check constraints, and triggers where appropriate

## Core Schema Structure

### 1. Tenant & Organization Management

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'free',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    UNIQUE(name),
    CONSTRAINT chk_plan_tier CHECK (plan_tier IN ('free', 'pro', 'enterprise', 'enterprise_plus'))
);

-- Organization settings with validation
CREATE TABLE organization_settings (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    sso_enabled BOOLEAN DEFAULT FALSE,
    sso_provider VARCHAR(50), -- 'saml', 'oidc', etc.
    sso_config JSONB,
    mfa_required BOOLEAN DEFAULT FALSE,
    session_timeout_minutes INTEGER DEFAULT 480,
    data_retention_days INTEGER DEFAULT 365,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Organization members/users
CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL, -- References auth service/users table
    role VARCHAR(50) NOT NULL,
    invited_by UUID REFERENCES organization_members(id),
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, active, suspended
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, user_id),
    CONSTRAINT chk_role CHECK (role IN ('owner', 'admin', 'member', 'viewer', 'billing_manager')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'active', 'suspended', 'removed'))
);

-- Organization invitations
CREATE TABLE organization_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    invited_by UUID NOT NULL REFERENCES organization_members(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ NULL,
    CONSTRAINT chk_role CHECK (role IN ('owner', 'admin', 'member', 'viewer', 'billing_manager'))
);
```

### 2. Projects & Repositories

```sql
-- Projects within organizations
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    UNIQUE(organization_id, slug),
    UNIQUE(organization_id, name)
);

-- Connected repositories (GitHub, GitLab, etc.)
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- 'github', 'gitlab', 'bitbucket', 'azure_devops'
    provider_id VARCHAR(255) NOT NULL, -- External ID from provider
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    webhook_id VARCHAR(255), -- For managing webhooks
    webhook_secret VARCHAR(255),
    enabled BOOLEAN DEFAULT TRUE,
    auto_analysis BOOLEAN DEFAULT TRUE,
    default_branch VARCHAR(100) DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, provider, provider_id),
    CONSTRAINT chk_provider CHECK (provider IN ('github', 'gitlab', 'bitbucket', 'azure_devops'))
);

-- Repository webhook events (for idempotency)
CREATE TABLE repository_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    provider_event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repository_id, provider_event_id)
);
```

### 3. Users & Authentication (Simplified - would typically link to external auth service)

```sql
-- Local user profiles (supplements external auth)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Would typically reference external auth provider ID (Auth0, Firebase, etc.)
    external_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url TEXT,
    timezone VARCHAR(50),
    locale VARCHAR(10),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ NULL,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(email)
);

-- API Keys for service-to-service authentication
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL, -- Who created the key
    name VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL, -- First 8 chars for display
    key_hash VARCHAR(255) NOT NULL, -- Bcrypt hash of full key
    permissions JSONB NOT NULL DEFAULT '{"projects": [], "permissions": []}',
    expires_at TIMESTAMPTZ NULL,
    last_used_at TIMESTAMPTZ NULL,
    usage_count INTEGER DEFAULT 0,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(key_prefix, key_hash) -- Prevent duplicate keys
);

-- API Key usage audit
CREATE TABLE api_key_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4. Roles & Permissions (RBAC System)

```sql
-- Roles (can be customized per organization)
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '{}', -- Fine-grained permissions
    is_system BOOLEAN DEFAULT FALSE, -- Built-in roles cannot be deleted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- Default system roles (created via migration/trigger)
-- admin: full access
-- member: standard user access
-- viewer: read-only access
-- billing_manager: billing and subscription management

-- User role assignments (many-to-many)
CREATE TABLE user_role_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES user_profiles(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NULL,
    PRIMARY KEY (organization_id, user_id, role_id) -- Prevent duplicate assignments
);
```

### 5. CI/CD Pipeline & Build Management

```sql
-- CI/CD Pipelines (configuration)
CREATE TABLE pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    repository_id UUID REFERENCES repositories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    yaml_config TEXT, -- Raw CI configuration
    trigger_events JSONB NOT NULL DEFAULT '["push", "pull_request"]', -- What triggers builds
    branches JSONB NOT NULL DEFAULT '["main", "master"]', -- Which branches to build
    variables JSONB DEFAULT '{}', -- Environment variables
    timeout_minutes INTEGER DEFAULT 60,
    retry_failed BOOLEAN DEFAULT FALSE,
    max_concurrent_builds INTEGER DEFAULT 10,
    queued BOOLEAN DEFAULT TRUE, -- Enable/disable queuing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, name)
);

-- Builds (execution instances)
CREATE TABLE builds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_sha VARCHAR(40) NOT NULL,
    commit_message TEXT,
    commit_author_name VARCHAR(255),
    commit_author_email VARCHAR(255),
    commit_authored_at TIMESTAMPTZ,
    branch VARCHAR(255) NOT NULL,
    tag VARCHAR(255), -- If triggered by tag
    pull_request_id VARCHAR(255), -- If triggered by PR
    pull_request_title VARCHAR(500),
    pull_request_target_branch VARCHAR(255),
    triggered_by VARCHAR(255), -- User or system that triggered
    trigger_event VARCHAR(50) NOT NULL, -- push, pull_request, tag, schedule, api
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, queued, running, success, failed, cancelled, timeout
    queue_position INTEGER, -- Position in queue if queued
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    estimated_start_time TIMESTAMPTZ NULL,
    estimated_finish_time TIMESTAMPTZ NULL,
    duration_ms INTEGER, -- Calculated when completed
    runner_id VARCHAR(255), -- Identifier of the runner that executed
    runner_labels JSONB, -- Labels of the runner
    logs_url TEXT, -- URL to full logs (if stored externally)
    artifacts_url TEXT, -- URL to artifacts (if stored externally)
    environment JSONB DEFAULT '{}', -- Build environment info
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled', 'timeout')),
    INDEX idx_builds_project_status (pipeline_id, status, created_at),
    INDEX idx_builds_commit_branch (commit_sha, branch),
    INDEX Echo builds_created_at (created_at)
);

-- Build stages (for stages within a pipeline)
CREATE TABLE build_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    duration_ms INTEGER,
    logs TEXT, -- or reference to external storage
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_stage_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'cancelled', 'skipped'))
);

-- Build steps (individual steps within stages)
CREATE TABLE build_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_stage_id UUID NOT NULL REFERENCES build_stages(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    command TEXT, -- The actual command/run command
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    duration_ms INTEGER,
    exit_code INTEGER, -- Exit code of the command
    logs TEXT, -- or reference to external storage
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_step_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'cancelled', 'skipped'))
);
```

### 6. Test Execution & Results

```sql
-- Test Suites (logical groupings of tests)
CREATE TABLE test_suites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_pattern VARCHAR(500), -- Glob pattern for test discovery
    timeout_seconds INTEGER DEFAULT 300,
    retry_attempts INTEGER DEFAULT 0,
    parallelism INTEGER DEFAULT 1, -- How many tests to run in parallel
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, name)
);

-- Test Features (for feature-based organization, like in Cucumber)
CREATE TABLE test_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_suite_id UUID NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path VARCHAR(1000), -- Path to feature file
    line_number INTEGER,
    tags JSONB DEFAULT '[]', -- Tags like @smoke, @regression
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(test_suite_id, file_path, line_number)
);

-- Test Scenarios (individual test scenarios)
CREATE TABLE test_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_feature_id UUID NOT NULL REFERENCES test_features(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    line_number INTEGER,
    keyword VARCHAR(50), -- Scenario, Scenario Outline, etc.
    steps_json JSONB, -- Detailed steps for complex scenarios
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(test_feature_id, name)
);

-- Test Cases (individual test cases - could be unit tests, etc.)
CREATE TABLE test_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_scenario_id UUID REFERENCES test_scenarios(id) ON DELETE SET NULL, -- Null for non-scenario tests
    test_suite_id UUID NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    class_name VARCHAR(500), -- For unit tests (class containing test)
    method_name VARCHAR(500), -- For unit tests (method name)
    file_path VARCHAR(1000), -- Path to test file
    line_number INTEGER,
    tags JSONB DEFAULT '[]',
    parameters JSONB DEFAULT '{}', -- For parameterized tests
    timeout_seconds INTEGER DEFAULT 30,
    retry_count INTEGER DEFAULT 0,
    flaky BOOLEAN DEFAULT FALSE, -- Flagged by AI as flaky
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Test Executions (individual test run results)
CREATE TABLE test_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
    test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL, -- passed, failed, skipped, errored, cancelled
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL,
    error_message TEXT,
    error_traceback TEXT, -- Stack trace or error details
    attachments_json JSONB DEFAULT '[]', -- References to screenshots, logs, etc.
    metrics JSONB DEFAULT '{}', -- Custom metrics (memory usage, etc.)
    retried BOOLEAN DEFAULT FALSE, -- Whether this was a retry attempt
    retry_of UUID REFERENCES test_executions(id), -- Original execution if this is a retry
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('passed', 'failed', 'skipped', 'errored', 'cancelled')),
    INDEX idx_test_executions_build_status (build_id, status),
    INDEX idx_test_executions_test_case (test_case_id),
    INDEX idx_test_executions_timing (started_at, completed_at)
);

-- Test Steps (for granular step-level reporting in BDD/frameworks)
CREATE TABLE test_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_execution_id UUID NOT NULL REFERENCES test_executions(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    name VARCHAR(500) NOT NULL,
    keyword VARCHAR(50, -- Given, When, Then, etc. for BDD
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMptz NOT NULL,
    duration_ms INTEGER NOT NULL,
    error_message TEXT,
    attachments_json JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_step_status CHECK (status IN ('passed', 'failed', 'skipped', 'errored'))
);
```

### 7. Artifacts & Media Storage References

```sql
-- General artifact table (references to objects in object storage)
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID REFERENCES builds(id) ON DELETE SET NULL,
    test_execution_id UUID REFERENCES test_executions(id) ON DELETE SET NULL,
    test_step_id UUID REFERENCES test_steps(id) ON DELETE SET NULL,
    artifact_type VARCHAR(50) NOT NULL, -- screenshot, video, trace, log, file, etc.
    file_name VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    storage_provider VARCHAR(50) NOT NULL, -- 'aws_s3', 'gcs', 'azure_blob', etc.
    bucket_name VARCHAR(255) NOT NULL,
    object_key VARCHAR(1000) NOT NULL, -- Full path in bucket
    version_id VARCHAR(255), -- For versioned storage systems
    checksum_md5 VARCHAR(32),
    checksum_sha256 VARCHAR(64),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NULL, -- For auto-expiration/temp files
    is_public BOOLEAN DEFAULT FALSE, -- Whether object is publicly accessible
    metadata JSONB DEFAULT '{}', -- Custom metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_artifact_type CHECK (
        artifact_type IN (
            'screenshot', 'video', 'trace', 'log', 'file', 
            'json', 'xml', 'csv', 'pdf', 'zip', 'unknown'
        )
    ),
    INDEX idx_artifacts_build (build_id),
    INDEX idx_artifacts_test_execution (test_execution_id),
    INDEX idx_artifacts_uploaded (uploaded_at)
);

-- Screenshots (specialized artifact type with additional metadata)
CREATE TABLE screenshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID UNIQUE NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    width INTEGER,
    height INTEGER,
    format VARCHAR(20), -- png, jpeg, etc.
    page_url TEXT, -- URL where screenshot was taken
    element_selector VARCHAR(500), -- CSS selector if element-specific
    full_page BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Videos (specialized artifact type)
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID UNIQUE NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    duration_seconds INTEGER,
    width INTEGER,
    height INTEGER,
    fps INTEGER,
    format VARCHAR(20), -- mp4, webm, etc.
    has_audio BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Traces (specialized artifact type for distributed tracing)
CREATE TABLE traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID UNIQUE NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    trace_id VARCHAR(255) NOT NULL,
    span_id VARCHAR(255) NOT NULL,
    trace_format VARCHAR(50) NOT NULL, -- 'jaeger', 'zipkin', 'opentelemetry'
    spans_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Logs (specialized artifact type)
CREATE TABLE logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID UNIQUE NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    log_level VARCHAR(20), -- trace, debug, info, warn, error, fatal
    line_count INTEGER,
    byte_size INTEGER,
    -- For log-specific querying, we might extract fields or use full-text search
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 8. AI Engine & Insights

```sql
-- AI Analysis Jobs
CREATE TABLE ai_analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'failure_analysis', 'flaky_detection', 'performance_regression', etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    input_data JSONB, -- Data fed into the AI model
    result_data JSONB, -- AI-generated results
    error_message TEXT,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    model_used VARCHAR(100), -- e.g., 'claude-3-opus-20240229'
    model_version VARCHAR(50),
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    INDEX idx_ai_jobs_build_status (build_id, status)
);

-- AI Insights (results from AI analysis)
CREATE TABLE ai_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
    insight_type VARCHAR(50) NOT NULL, -- 'root_cause', 'flaky_test', 'performance_regression', 'impact_analysis'
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1), -- 0.0 to 1.0
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    affected_entities JSONB, -- What tests, commits, files are affected
    suggested_actions JSONB, -- Array of recommended actions
    evidence JSONB, -- Supporting evidence for the conclusion
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    INDEX idx_ai_insights_build_type (build_id, insight_type),
    INDEX idx_ai_insights_severity (severity),
    INDEX idx_ai_insights_created (created_at)
);

-- Flaky Test Tracking
CREATE TABLE flaky_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    detection_count INTEGER DEFAULT 1, -- How many times flakiness detected
    pass_rate DECIMAL(5,4), -- Percentage of passes (0.0000 to 1.0000)
    failure_pattern JSONB, -- Pattern of failures (e.g., every 5th run)
    environment_conditions JSONB, -- Conditions under which it fails
    is_confirmed BOOLEAN DEFAULT FALSE, -- Whether AI/human confirmed it's flaky
    enabled BOOLEAN DEFAULT TRUE, -- Whether to track this test
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(test_case_id),
    INDEX idx_flaky_tests_pass_rate (pass_rate),
    INDEX idx_flaky_tests_detected (last_detected_at)
);

-- Performance Baselines
CREATE TABLE performance_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
    baseline_duration_ms INTEGER NOT NULL,
    sample_size INTEGER NOT NULL, -- Number of runs used to establish baseline
    standard_dev_ms INTEGER,
    confidence_level DECIMAL(3,2) DEFAULT 0.95, -- 95% confidence
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ NOT NULL, -- When baseline expires
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(test_case_id),
    INDEX idx_performance_baselines_valid (valid_until)
);
```

### 9. Notifications & Alerting

```sql
-- Notification Templates
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    template_type VARCHAR(50) NOT NULL, -- 'email', 'slack', 'teams', 'webhook', 'sms'
    subject_template VARCHAR(1000), -- For email
    body_template TEXT NOT NULL, -- Template with handlebars or similar
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE, -- Default for type if none specified
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_template_type CHECK (
        template_type IN ('email', 'slack', 'teams', 'webhook', 'sms', 'in_app')
    ),
    UNIQUE(organization_id, template_type, name)
);

-- Notification Channels (configured destinations)
CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    channel_type VARCHAR(50) NOT NULL, -- 'email', 'slack', 'teams', 'webhook', 'sms'
    configuration JSONB NOT NULL, -- Connection details, credentials (encrypted)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name),
    CONSTRAINT chk_channel_type CHECK (
        channel_type IN ('email', 'slack', 'teams', 'webhook', 'sms', 'in_app')
    )
);

-- Notification Preferences (per user)
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL, -- 'build_failed', 'test_failed', 'new_insight', etc.
    channel_type VARCHAR(50) NOT NULL, -- Matches notification_channels.channel_type
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMptz NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, event_type, channel_type),
    CONSTRAINT chk_event_type CHECK (
        event_type IN (
            'build_started', 'build_success', 'build_failed', 'build_cancelled',
            'test_passed', 'test_failed', 'test_skipped',
            'new_ai_insight', 'flaky_test_detected', 'performance_regression',
            'deployment_status', 'system_alert', 'weekly_summary'
        )
    )
);

-- Notification Queue (for async processing)
CREATE TABLE notification_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_channel_id UUID NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
    recipient_identifier VARCHAR(500), -- Email address, Slack user ID, etc.
    template_id UUID REFERENCES notification_templates(id) ON DELETE SET NULL,
    subject VARCHAR(1000),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, sending, sent, failed, cancelled
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    next_attempt_at TIMESTAMPTZ, -- For retry scheduling
    sent_at TIMESTAMPTZ NULL,
    error_message TEXT,
    metadata JSONB DEFAULT '{}', -- Additional context for processing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')),
    INDEX idx_notification_queue_status (status, next_attempt_at),
    INDEX idx_notification_queue_created (created_at)
);

-- Sent Notifications (audit trail)
CREATE TABLE sent_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_queue_id UUID NOT NULL REFERENCES notification_queue(id) ON DELETE CASCADE,
    recipient_identifier VARCHAR(500),
    subject VARCHAR(1000),
    body TEXT,
    channel_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- sent, failed, bounced, etc.
    provider_response JSONB, -- Response from email/SMS/etc provider
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('sent', 'failed', 'bounced', 'delayed', 'queued'))
);
```

### 10. Webhooks & Integrations

```sql
-- Outbound Webhooks
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(2000) NOT NULL,
    secret VARCHAR(255), -- For HMAC signature verification
    http_method VARCHAR(10) DEFAULT 'POST',
    headers JSONB DEFAULT '{}', -- Custom headers to send
    events JSONB NOT NULL, -- Array of event types to subscribe to
    active BOOLEAN DEFAULT TRUE,
    retry_count INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 60,
    timeout_seconds INTEGER DEFAULT 30,
    ssl_verification BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name),
    CONSTRAINT chk_http_method CHECK (http_method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'))
);

-- Webhook Delivery Log
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    http_status_code INTEGER,
    response_body TEXT,
    attempt_number INTEGER DEFAULT 1,
    delivered_at TIMESTAMPTZ NULL,
    failed_at TIMESTAMPTZ NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_event_type CHECK (
        event_type IN (
            'build.started', 'build.completed', 'build.failed', 'build.cancelled',
            'test.passed', 'test.failed', 'test.skipped',
            'ai.insight.generated', 'flaky.test.detected',
            'deployment.started', 'deployment.completed', 'deployment.failed'
        )
    ),
    INDEX idx_webhook_deliveries_webhook (webhook_id),
    INDEX idx_webhook_deliveries_created (created_at)
);

-- Incoming Webhooks (for receiving data from external systems)
CREATE TABLE incoming_webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(255) NOT NULL UNIQUE, -- Unique endpoint path
    secret VARCHAR(255), -- For verifying signature
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    last_received_at TIMESTAMPTZ NULL,
    total_received INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Incoming Webhook Requests Log
CREATE TABLE incoming_webhook_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incoming_webhook_id UUID NOT NULL REFERENCES incoming_webhooks(id) ON DELETE CASCADE,
    http_method VARCHAR(10) NOT NULL,
    headers JSONB NOT NULL,
    query_params JSONB,
    payload JSONB,
    client_ip INET,
    user_agent TEXT,
    signature_valid BOOLEAN,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_http_method CHECK (http_method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'))
);
```

### 11. Audit & Compliance

```sql
-- Comprehensive Audit Log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL, -- Null for system actions
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100), -- What type of entity was affected
    entity_id UUID, -- ID of the affected entity
    action VARCHAR(50) NOT NULL, -- CREATE, READ, UPDATE, DELETE, LOGIN, etc.
    changes JSONB, -- Diff of what changed (for UPDATE/DELETE)
    metadata JSONB DEFAULT '{}', -- Additional context
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255), -- For tracing requests across services
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_audit_log_org_time (organization_id, created_at),
    INDEX idx_audit_log_entity (entity_type, entity_id),
    INDEX idx_audit_log_user_time (user_id, created_at),
    CONSTRAINT chk_action CHECK (
        action IN (
            'CREATE', 'READ', 'UPDATE', 'DELETE', 
            'LOGIN', 'LOGOUT', 'LOGIN_FAILED',
            'API_KEY_CREATED', 'API_KEY_USED', 'API_KEY_REVOKED',
            'WEBHOOK_CREATED', 'WEBHOOK_UPDATED', 'WEBHOOK_DELETED',
            'PERMISSION_GRANTED', 'PERMISSION_REVOKED',
            'SETTINGS_UPDATED'
        )
    )
);

-- Data Retention Policies
CREATE TABLE data_retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL, -- 'builds', 'test_executions', 'artifacts', 'logs', etc.
    retention_days INTEGER NOT NULL,
    archive_before_delete BOOLEAN DEFAULT FALSE,
    archive_destination VARCHAR(100), -- 'glacier', 'nearline', etc.
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, data_type),
    CONSTRAINT chk_data_type CHECK (
        data_type IN (
            'builds', 'test_executions', 'test_steps', 
            'artifacts', 'logs', 'audit_log', 'notifications',
            'webhook_deliveries', 'api_key_usage'
        )
    )
);

-- GDPR / Data Subject Requests
CREATE TABLE data_subject_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    request_type VARCHAR(50) NOT NULL, -- 'access', 'rectification', 'erasure', 'portability', 'restriction'
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, rejected
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    notes TEXT,
    fulfilled_by UUID REFERENCES user_profiles(id),
    legal_basis VARCHAR(200), -- Legal basis for processing request
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_request_type CHECK (
        request_type IN ('access', 'rectification', 'erasure', 'portability', 'restriction')
    ),
    CONSTRAINT chk_status CHECK (
        status IN ('pending', 'processing', 'completed', 'rejected')
    )
);
```

### 12. Plugin System

```sql
-- Plugin Registrations
CREATE TABLE plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    version VARCHAR(50) NOT NULL,
    author VARCHAR(255),
    homepage_url TEXT,
    repository_url TEXT,
    license VARCHAR(100),
    entry_point VARCHAR(500), -- Main entry point for plugin
    permissions JSONB NOT NULL, -- What permissions the plugin requires
    configuration_schema JSONB, -- JSON Schema for plugin configuration
    default_configuration JSONB, -- Default values for configuration
    tags JSONB DEFAULT '[]', -- For categorization/search
    is_active BOOLEAN DEFAULT TRUE,
    is_builtin BOOLEAN DEFAULT FALSE, -- Built-in platform plugins
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_health_check TIMESTAMPTZ NULL,
    health_status VARCHAR(20), -- 'healthy', 'unhealthy', 'unknown'
    UNIQUE(organization_id, name),
    INDEX idx_plugins_organization (organization_id),
    INDEX idx_plugins_active (is_active)
);

-- Plugin Configurations (per organization/instance)
CREATE TABLE plugin_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id UUID NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    configuration JSONB NOT NULL, -- User-provided configuration
    is_enabled BOOLEAN DEFAULT TRUE,
    configured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(plugin_id, organization_id)
);

-- Plugin Execution Logs
CREATE TABLE plugin_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id UUID NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    trigger_event VARCHAR(100), -- What triggered the plugin execution
    input_data JSONB, -- Input data provided to plugin
    output_data JSONB, -- Output data from plugin
    status VARCHAR(20) NOT NULL, -- 'success', 'error', 'timeout'
    error_message TEXT,
    execution_time_ms INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (status IN ('success', 'error', 'timeout')),
    INDEX idx_plugin_executions_plugin (plugin_id),
    INDEX idx_plugin_executions_created (created_at)
);
```

### 13. Feature Flags & Experimentation

```sql
-- Feature Flags
CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT FALSE,
    rollout_percentage DECIMAL(5,2) DEFAULT 0.00, -- 0-100% rollout
    targeting_rules JSONB, -- Conditions for who sees the feature
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name),
    CONSTRAINT chk_rollout_percentage CHECK (rollout_percentage BETWEEN 0 AND 100)
);

-- Feature Flag Usage (for analytics)
CREATE TABLE feature_flag_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_flag_id UUID NOT NULL REFERENCES feature_flags(id) ON DELETE CASCADE,
    user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    enabled BOOLEAN NOT NULL, -- Whether feature was enabled for this user/request
    context JSONB, -- Context used for evaluation (user attributes, etc.)
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_feature_flag_usage_flag (feature_flag_id),
    INDEX idx_feature_flag_usage_evaluated (evaluated_at)
);
```

### 14. Billing & Subscription (Simplified)

```sql
-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    plan_tier VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'active', 'past_due', 'canceled', 'unpaid', 'trialing'
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    trial_start TIMESTAMPTZ NULL,
    trial_end TIMESTAMPTZ NULL,
    canceled_at TIMESTAMPTZ NULL,
    ended_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id),
    CONSTRAINT chk_status CHECK (
        status IN ('active', 'past_due', 'canceled', 'unpaid', 'trialing', 'paused')
    ),
    CONSTRAINT chk_plan_tier CHECK (
        plan_tier IN ('free', 'pro', 'enterprise', 'enterprise_plus')
    )
);

-- Subscription Items (for add-ons, usage-based pricing)
CREATE TABLE subscription_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    price_id VARCHAR(255) NOT NULL, -- Reference to pricing system
    quantity INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Usage Records (for metered billing)
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    quantity INTEGER NOT NULL,
    action VARCHAR(50), -- 'increment', 'set'
    description TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_usage_records_subscription_time (subscription_id, timestamp)
);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL,
    amount_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL, -- 'draft', 'open', 'paid', 'void', 'uncollectible'
    due_date TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ NULL,
    attempt_count INTEGER DEFAULT 0,
    next_payment_attempt TIMESTAMPTZ NULL,
    hosted_invoice_url TEXT, -- Link to hosted invoice (Stripe, etc.)
    invoice_pdf_url TEXT, -- Downloadable PDF
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (
        status IN ('draft', 'open', 'paid', 'void', 'uncollectible')
    )
);
```

### 15. System & Configuration

```sql
-- System Settings (global configuration)
CREATE TABLE system_settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES user_profiles(id) -- Who last updated
);

-- Maintenance Windows
CREATE TABLE maintenance_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    affected_services JSONB DEFAULT '[]', -- Which services are affected
    impact_level VARCHAR(20) NOT NULL, -- 'none', 'minimal', 'moderate', 'severe'
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern JSONB, -- Cron-like pattern for recurring maintenance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_impact_level CHECK (
        impact_level IN ('none', 'minimal', 'moderate', 'severe')
    )
);

-- System Health Checks
CREATE TABLE health_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL,
    check_type VARCHAR(50) NOT NULL, -- 'database', 'cache', 'external_api', 'disk_space', etc.
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'unhealthy', 'unknown'
    response_time_ms INTEGER,
    message TEXT,
    details JSONB,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_health_checks_service (service_name),
    INDEX idx_health_checks_checked (checked_at),
    CONSTRAINT chk_status CHECK (
        status IN ('healthy', 'degraded', 'unhealthy', 'unknown')
    )
);

-- Database Migrations Tracking
CREATE TABLE schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);
```

## Indexing Strategy

### Critical Indexes for Performance

```sql
-- Partitioning strategy for large tables (example for test_executions)
-- In practice, would use declarative partitioning or pg_partman

CREATE INDEX idx_test_executions_build_lookup ON test_executions(build_id, status);
CREATE INDEX idx_test_executions_time_range ON test_executions(started_at, completed_at);
CREATE INDEX idx_test_executions_test_case_lookup ON test_executions(test_case_id, status);
CREATE INDEX idx_test_executions_created ON test_executions(created_at);

-- Build queries
CREATE INDEX idx_builds_pipeline_lookup ON builds(pipeline_id, status, created_at DESC);
CREATE INDEX idx_builds_recent ON builds(created_at DESC) WHERE status IN ('running', 'pending', 'queued');
CREATE INDEX idx_builds_commit_lookup ON builds(commit_sha, branch);

-- Artifact queries
CREATE INDEX idx_artifacts_lookup ON artifacts(build_id, test_execution_id, artifact_type);
CREATE INDEX idx_artifacts_uploaded ON artifacts(uploaded_at) WHERE expires_at IS NULL OR expires_at > NOW();

-- Audit queries
CREATE INDEX idx_audit_lookup ON audit_log(organization_id, created_at DESC) WHERE created_at > NOW() - INTERVAL '90 days';

-- AI insights
CREATE INDEX idx_ai_insights_lookup ON ai_insights(build_id, insight_type, created_at DESC);
CREATE INDEX idx_ai_insights_severity_time ON ai_insights(severity, created_at DESC);

-- Notification queries
CREATE INDEX idx_notification_queue_processing ON notification_queue(status, next_attempt_at) WHERE status = 'pending';
CREATE INDEX idx_sent_notifications_lookup ON sent_notifications(created_at DESC) WHERE created_at > NOW() - INTERVAL '30 days';

-- Webhook deliveries
CREATE INDEX idx_webhook_deliveries_retry ON webhook_deliveries(webhook_id, attempt_number, created_at DESC) WHERE delivered_at IS NULL;

-- Plugin executions
CREATE INDEX idx_plugin_executions_lookup ON plugin_executions(plugin_id, organization_id, created_at DESC);
```

## Partitioning Strategy (For Large Tables)

For tables expected to grow very large (billions of rows), consider partitioning:

```sql
-- Example: Partition test_executions by month (using declarative partitioning)
CREATE TABLE test_executions_y2026m07 PARTITION OF test_executions
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE test_executions_y2026m08 PARTITION OF test_executions
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

-- And so on for future months
-- In practice, use pg_partman or similar for automated partition management
```

## Security Considerations

### Row Level Security (RLS) for Multi-tenancy
```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;
-- ... and so on for all organization-scoped tables

-- Create policies
CREATE POLICY org_isolation_on_organizations ON organizations
    USING (id = current_setting('app.current_organization_id')::uuid);

CREATE POLICY org_isolation_on_projects ON projects
    USING (organization_id = current_setting('app.current_organization_id')::uuid);

-- Similar patterns for other tables
```

### Data Encryption
- **At Rest**: Use PostgreSQL's built-in encryption or filesystem-level encryption
- **In Transit**: Enforce SSL/TLS for all connections
- **Field-Level**: Consider encrypting sensitive fields like API keys, secrets, PII
- **Key Management**: Integrate with HashiCorp Vault, AWS KMS, or Azure Key Vault

### Connection Security
- Enforce SSL connections: `sslmode=require` in connection strings
- Use connection pooling (PgBouncer) with TLS termination
- Implement network segmentation and private networking

## Maintenance & Operations

### Backup Strategy
- **Physical Backups**: Regular base backups using pg_basebackup
- **WAL Archiving**: Continuous archiving of WAL files for point-in-time recovery
- **Logical Backups**: Regular pg_dump for selective recovery
- **Cross-Region Replication**: For disaster recovery
- **Backup Testing**: Regular restore testing procedures

### Monitoring & Alerting
- **Connection Monitoring**: Track active connections, idle connections
- **Query Performance**: Monitor slow queries using pg_stat_statements
- **Replication Lag**: Monitor replica lag for read replicas
- **Storage Utilization**: Track disk usage and forecast growth
- **Backup Verification**: Automated backup validation

### Performance Optimization
- **Regular VACUUM**: Schedule autovacuum tuning for write-heavy tables
- **Index Maintenance**: Regular REINDEX for bloated indexes
- **Statistics Updates**: Ensure ANALYZE runs regularly
- **Connection Pooling**: Properly sized pool for application needs
- **Query Optimization**: Use EXPLAIN ANALYZE for slow queries

## Migration & Evolution Strategy

### Schema Versioning
- Use migration tool (Flyway, Liquibase, or custom)
- Each migration gets a version number and description
- Migrations are immutable once applied
- Rollback strategies for critical migrations

### Data Migration Patterns
- **Blue-Green Deployment**: For zero-downtime schema changes
- **Expansion/Contraction Pattern**: Add new columns before removing old ones
- **Shadow Tables**: For complex data transformations
- **Event Sourcing**: For rebuilding read models when needed

### Scaling Considerations
- **Read Replicas**: For read-heavy workloads (analytics, reporting)
- **Connection Pooling**: PgBouncer or similar for efficient connection use
- **Caching Layer**: Redis for frequently accessed data
- **Search Optimization**: Consider Elasticsearch for text search if needed
- **Archiving Strategy**: Move old data to cheaper storage (S3 Glacier, etc.)

## Sample Queries

### Build Dashboard Query
```sql
SELECT 
    b.id,
    b.status,
    b.started_at,
    b.completed_at,
    b.duration_ms,
    p.name as pipeline_name,
    COUNT(te.id) as total_tests,
    COUNT(CASE WHEN te.status = 'passed' THEN 1 END) as passed_tests,
    COUNT(CASE WHEN te.status = 'failed' THEN 1 END) as failed_tests,
    COUNT(CASE WHEN te.status = 'skipped' THEN 1 END) as skipped_tests
FROM builds b
JOIN pipelines p ON b.pipeline_id = p.id
LEFT JOIN test_executions te ON b.id = te.build_id
WHERE b.project_id = $1
    AND b.created_at >= $2
    AND b.created_at < $3
GROUP BY b.id, b.status, b.started_at, b.completed_at, b.duration_ms, p.name
ORDER BY b.started_at DESC
LIMIT 50;
```

### Flaky Test Report
```sql
SELECT 
    tc.name as test_name,
    ts.name as suite_name,
    ft.pass_rate,
    ft.detection_count,
    ft.first_detected_at,
    ft.last_detected_at,
    array_agg(distinct ei.error_message) filter (where ei.error_message is not null) as recent_errors
FROM flaky_tests ft
JOIN test_cases tc ON ft.test_case_id = tc.id
JOIN test_suites ts ON tc.test_suite_id = ts.id
LEFT JOIN test_executions te ON tc.id = te.test_case_id
LEFT JOIN (
    SELECT test_execution_id, error_message 
    FROM test_executions 
    WHERE error_message IS NOT NULL 
    ORDER BY created_at DESC 
    LIMIT 3
) ei ON te.id = ei.test_execution_id
WHERE ft.is_confirmed = true
    AND ts.project_id = $1
GROUP BY tc.name, ts.name, ft.pass_rate, ft.detection_count, ft.first_detected_at, ft.last_detected_at
ORDER BY ft.detection_count DESC, ft.pass_rate ASC
LIMIT 20;
```

### AI Insights Summary
```sql
SELECT 
    ai.insight_type,
    ai.severity,
    COUNT(*) as count,
    AVG(ai.confidence_score) as avg_confidence
FROM ai_insights ai
JOIN builds b ON ai.build_id = b.id
WHERE b.project_id = $1
    AND ai.created_at >= $2
    AND ai.created_at < $3
GROUP BY ai.insight_type, ai.severity
ORDER BY 
    CASE ai.severity 
        WHEN 'critical' THEN 4 
        WHEN 'high' THEN 3 
        WHEN 'medium' THEN 2 
        ELSE 1 
    END DESC,
    count DESC;
```

## Conclusion

This schema provides a robust foundation for the QA Vision platform, implementing:

1. **Multi-tenancy** with strong isolation between organizations
2. **Comprehensive auditability** for compliance and debugging
3. **Scalability** through thoughtful indexing and partitioning strategies
4. **Extensibility** via JSONB fields and plugin architecture
5. **Performance** optimization for common query patterns
6. **Data integrity** through constraints and proper relationships
7. **Flexibility** to accommodate various testing frameworks and CI systems

The schema is designed to evolve with the application's needs while maintaining data consistency and performance at scale.