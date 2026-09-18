# Immediate Next Steps for QA Vision Architecture Evolution

**Corrected 2026-09-17:** this checklist had gone stale — several items below were marked incomplete despite already being done (directory reorg), and the Organization Service line described a design that shipped somewhat differently in practice. Checkboxes below reflect actual verified repo state, not prior assumptions. See `ARCHITECTURE_EVOLUTION_SUMMARY.md` for the corresponding, also-corrected service-status summary.

## Phase 0: Foundation Setup

### 1. Create Domain Directory Structure
- [x] Create top-level domain directories:
  - platforms/
  - integrations/
  - execution/
  - intelligence/
  - collaboration/
  - administration/
  - [ ] shared/ — directory does **not** exist; still not done (see #3 below, also still not done)

### 2. Reorganize Existing Code
- [x] Move `src/services/auth-service/` → `platforms/auth-service/`
- [x] Move `ai-engine/` → `intelligence/ai-engine/`
- [x] Update all internal imports and references (auth-service builds and runs from its new location)

### 3. Establish Shared Foundations
- [ ] Create `shared/logging.py` (consolidate existing logging config)
- [ ] Create `shared/config.py` (consolidate existing config)
- [ ] Create `shared/exceptions.py` (consolidate existing exceptions)
- [ ] Create `shared/database.py` (consolidate existing DB setup)
- [ ] Create `shared/models/base.py` with BaseModel/TenantAwareModel/AuditableModel

None of this exists. Every real service so far (auth-service, organization-service) has independently reimplemented its own config/db/base-model boilerplate rather than sharing it — worth doing before a third real service is built, to avoid a third copy of the same code.

### 4. Update Authentication Service for Platform Domain
- [x] User model has `tenant_id` (`platforms/auth-service/auth-service/src/auth/models/user.py`)
- [x] Auth Service endpoints work from the new structure (tests pass)
- [x] Authentication flows tested (auth-service's own test suite)

## Phase 1: Platform Completion (Weeks 1-4)

### 1. Organization Service (platforms/organization-service/) — ✅ DONE (2026-09-16/17, differs from this checklist's original shape)
- [x] Organization model (id, name, slug, plan_tier, created_at, updated_at, deleted_at for soft-delete)
- [x] Membership implemented as `OrganizationMember` (role/status per user per org) rather than a separate `Team` entity — same underlying need (who belongs to an org and with what permissions), different shape than originally sketched here
- [x] CRUD operations for organizations and memberships
- [x] Organization-scoping enforced via a `require_org_role` FastAPI dependency (404 not-a-member / 403 wrong-role)
- [x] API endpoints for organization + membership management
- [x] Unit and integration tests (51, all passing)
- [ ] Invitation system — **specced, not yet built**: `docs/superpowers/specs/2026-09-17-organization-invitations-design.md`
- [ ] Per-org SSO/MFA/session settings — not yet even specced

### 2. Project Service (projects/project-service/)
- [ ] Create Project model (with organization_id)
- [ ] Implement basic CRUD operations
- [ ] Add project-scoping to authentication
- [ ] Create API endpoints
- [ ] Write tests

### 3. User & Team Services
- [ ] User Service (enhanced profile management)
- [ ] Team Service (membership, roles, permissions)
- [ ] Implement invitation system
- [ ] Add RBAC utilities

## Phase 2: Integrations Foundation (Weeks 3-6)

### 1. Webhook Service (integrations/webhook-service/)
- [ ] Create webhook endpoint receiver
- [ ] Implement event validation and transformation
- [ ] Create webhook registration and management APIs
- [ ] Add retry mechanism and dead letter queue
- [ ] Write tests

### 2. Version Control Integrations
- [ ] GitHub Integration (integrations/github-integration/)
- [ ] GitLab Integration (integrations/gitlab-integration/)
- [ ] Basic repo tracking, webhook handling, event processing

### 3. Plugin Framework (integrations/plugin-framework/)
- [ ] Plugin registration and discovery mechanism
- [ ] Plugin execution sandbox
- [ ] Configuration management for plugins
- [ ] Basic plugin lifecycle management

## Phase 3: Intelligence Core Refactor (Weeks 4-8)

### 1. Processing Layer Enhancement (intelligence/processing/)
- [ ] Enhance Data Preparation Service:
  - Broaden scope from ML data prep to general quality data processing
  - Add data normalization, validation, correlation, enrichment functions
  - Create generic processing pipeline framework
  - Maintain backward compatibility with existing API v1
  - Introduce API v2 for enhanced processing capabilities

### 2. Knowledge Layer Enhancement (intelligence/knowledge/)
- [ ] Enhance Feature Store Service:
  - Shift from ML feature storage to general knowledge repository
  - Expand entity model to include executions, failures, fixes, resolutions
  - Add historical tracking and trending capabilities
  - Maintain backward compatibility with existing API v1
  - Introduce API v2 for enhanced knowledge operations

### 3. AI Engine Refactor (intelligence/ai-engine/)
- [ ] Keep existing services intact during transition
- [ ] Begin migrating to new structure incrementally:
  - Model Management Service → Intelligence/AI Engine/Model Management
  - Training Pipeline Service → Intelligence/AI Engine/Training Pipeline  
  - Inference Service → Intelligence/AI Engine/Inference
  - etc.
- [ ] Maintain API compatibility during transition

## Success Criteria for Each Phase
- All existing tests continue to pass
- New services have ≥80% test coverage
- API documentation is updated for all changes
- No breaking changes without proper versioning/deprecation
- Performance benchmarks maintained or improved