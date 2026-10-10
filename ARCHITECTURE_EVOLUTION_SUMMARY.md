# QEOS Architecture Evolution - Executive Summary

Snapshot of 2026-09-17; current state: README.md, TECHNICAL_SPECIFICATION.md, the blueprint banner.

**Note (2026-09-17):** This document previously marked most Phase 1 services "✅ Complete." An audit that session found 11 of 15 sampled services (including Organization/Project/User/Team/Billing) were unmodified, single-commit copies of `auth-service` — same `User`/`Session`/`OAuthAccount` models, same `auth.py`/`sso.py` endpoints, zero domain logic — not real implementations. Statuses below have been corrected to reflect actual code state, verified by reading the source, not by trusting prior status markers in this file.

## Key Accomplishments - Phase 0: Foundation (Completed)
- **Established target domain-based repository structure** with directories for platforms, integrations, execution, intelligence, collaboration, administration
- **Successfully migrated validated services** to their new domain-aligned locations:
  - Authentication Service: `src/services/auth-service/` → `platforms/auth-service/auth-service/`
  - AI Engine: `ai-engine/` → `intelligence/ai-engine/` (preserving all subcomponents)
- **Maintained integrity** of the migrated auth service:
  - Preserved all functionality including JWT auth, RBAC, SSO framework
  - Updated internal imports, Dockerfile references, and configurations
- **NOT actually done, despite earlier claims below this line in prior versions of this document:**
  - `shared/lib/`, `shared/contracts/`, `shared/events/` — none of these directories exist in the repository. There is no shared foundation for logging, config, exceptions, database setup, or event schemas, despite being referenced as if they existed.
  - "Documentation consistency between Architecture Blueprint v1.0 and Technical Specification" was never independently verified against the ADRs; a separate review found the blueprint and other planning docs disagree with each other and with the current repo state in several places (see `NEXT_STEPS.md`'s corrected notes).

## Current Progress - Phase 1: Core Platform & Intelligence

### Platform Services:
- ✅ **Authentication Service**: Complete (real implementation — JWT, SSO, RBAC, tests match its README)
- ✅ **Organization Service**: Complete (built for real 2026-09-16/17 — Organization/Membership CRUD, role-gated access, auth-service integration, migrations, 51 tests, reviewed and merged to master). Follow-up sub-projects (`organization_invitations`, `organization_settings`/SSO-MFA config) are specced/in progress separately, see `docs/superpowers/specs/`.
- ❌ **Project Service**: Not started — `platforms/project-service/` is an unmodified auth-service clone (single commit, no domain logic)
- ❌ **User Service**: Not started — same clone pattern
- ❌ **Team Service**: Not started — same clone pattern
- ❌ **Billing/Subscription Service**: Not started — same clone pattern (two copies exist: `billing-service/` and `billing-service.backup/`, both clones)

### Intelligence Core:
- ❌ **Observability collector and storage**: Not started — `intelligence/observability-service/` is an auth-service clone
- ❌ **Knowledge repository and management**: Not started — `intelligence/knowledge-service/` is an auth-service clone
- ❌ **Analytics capabilities**: Not started — `intelligence/analytics-service/` is an auth-service clone (also ships unrelated vendored `dm.xmlsec.binding` junk and a `-temp` duplicate directory)
- ❌ **Insight Generation Service**: Not started — `intelligence/insight-generation-service/` is an auth-service clone
- ❌ **Prediction/Model Management Service**: Not started — `intelligence/prediction-service/` is an auth-service clone
- 🟡 **Feature Store Service** (`intelligence/ai-engine/services/feature_store`): Partial — thin but genuinely distinct code, not a clone; not further audited for completeness

### Cross-cutting infrastructure (see also `GAPS_ASSESSMENT.md`, which is honest about most of this):
- No CI/CD pipeline beyond a single CodeQL security scan
- No `shared/` foundation (see above)
- No root `docker-compose.yml` wiring services together
- No API gateway, service mesh, secrets manager, centralized logging/alerting, schema registry, feature flags, autoscaling, or backup/DR strategy

## What Actually Happened in Past Sessions Claiming "Immediate Next Steps (Completed)"

Prior versions of this document listed items like "Created comprehensive documentation for Insight Generation Service," "Analytics Service," "Model Management Service," "Observability... Service," "User Service," "Team Service" as completed next steps. What this meant in practice: a `README.md` was written for each service describing features and endpoints that **do not exist in the code** — the services themselves remained untouched auth-service clones underneath those READMEs. This is the exact "documentation theater" pattern flagged above. Writing a README is not equivalent to implementing a service, and this file previously conflated the two.

## Verification Checkpoint (for any future "complete" claim in this document)

Before marking a service complete, verify by reading the actual source, not by trusting a prior status marker:
- Does the service have domain-specific models, not `User`/`Session`/`OAuthAccount`?
- Does its git history show more than the single mass-reorg commit?
- Do its tests exercise real behavior against its own domain logic?
- Is its README describing code that actually exists?
