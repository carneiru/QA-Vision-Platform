# QEOS Architecture Evolution

## 1. Purpose
This document describes the evolution of QEOS from its initial AI Engine-focused architecture to an AI-native Quality Engineering Operating System. It captures the strategic decisions, migration approach, and progress toward a business capability-driven architecture that aligns with enterprise standards while preserving existing investments.

## 2. Drivers
- **Business Need**: Shift from point solutions to an integrated quality engineering platform
- **Technical Debt**: Initial architecture was AI-engine centric, lacking clear separation of concerns
- **Market Demand**: Enterprise customers require a comprehensive, scalable quality operations system
- **Scalability Requirements**: Need to support 100+ engineer organizations with independent team ownership
- **Technology Evolution**: Opportunity to adopt cloud-native, event-driven patterns

## 3. Guiding Principles
- **Preserve Existing Work**: Never discard validated architecture; migrate rather than rewrite
- **Business Capability First**: Organize around business capabilities, not technical layers or lifecycle phases
- **Incremental Evolution**: Support coexistence of old and new structures during transition
- **Operational Justification**: Create services only when justified by independent scalability, deployment, ownership, security, or technology needs
- **Domain-Driven Design**: Align code structure with bounded contexts and ubiquitous language
- **Avoid Artificial Microservices**: Prevent service proliferation without operational necessity
- **Backward Compatibility**: Maintain API contracts and data migration compatibility

## 4. Current Architecture (Baseline)
The baseline architecture consists of:
- **AI Engine Foundation**: Data preparation, feature store, shared components
- **Authentication Service**: JWT-based auth service with SSO framework
- **Shared Kernel Emerging**: Initial structuring of shared libraries, contracts, and events
- **Domain Placeholders": Empty directories for platforms, integrations, execution, intelligence, collaboration, administration
- **Technology Stack**: Python/FastAPI services, PostgreSQL, planned Kafka/event streaming

Detailed component inventory:
- Authentication Service: `src/services/auth-service/` → migrated to `platforms/auth-service/`
- AI Engine: `ai-engine/` → migrated to `intelligence/ai-engine/` with subcomponents:
  - Data Preparation Service
  - Feature Store Service  
  - Shared components (config, database, exceptions, logging)
- Shared Foundation: `shared/` with subdirectories `lib/`, `contracts/`, `events/`
- Domain scaffolding: `platforms/`, `integrations/`, `execution/`, `intelligence/`, `collaboration/`, `administration/`

## 5. Target Architecture
The target architecture is defined in the Architecture Blueprint v1.0.

## 6. Workstreams
Parallel workstreams enable efficient execution:

### 6.1 Platform Services Workstream
- Organization, Project, User/Team, Billing services
- Shared authentication & authorization framework
- Tenant isolation implementation

### 6.2 Intelligence Core Workstream
- Knowledge management foundation
- Insight generation pipeline
- Analytics and metrics collection
- Event stream processing infrastructure

### 6.3 Integration Workstream
- Webhook dispatch mechanism
- First adapters (GitHub, GitLab)
- Adapter SDK development
- Security and credential management

### 6.4 Execution Workstream
- Test case CRUD operations
- Distributed execution engine
- Environment provisioning (via IaC/tools)
- Artifact storage and retrieval

### 6.5 Collaboration Workstream
- Dashboard widget framework
- Reporting engine
- Notification delivery system
- Real-time collaboration features

### 6.6 Administration Workstream
- Audit logging infrastructure
- Role-based access control
- Configuration management
- Compliance reporting templates

### 6.7 Shared Infrastructure Workstream
- Observability stack (Loki, Tempo, Prometheus, Grafana)
- Service mesh (Istio/Linkerd)
- API Gateway (Kong)
- Secrets management (Vault)
- CI/CD pipelines (GitHub Actions)
- Schema Registry (Apicurio)

## 7. Architectural Decisions
Key decisions made during the evolution:

### 7.1 Domain Structure Decision
**Decision**: Organize top-level directories by business capability rather than technical layer or lifecycle phase.  
**Rationale**: Enables team autonomy, aligns with Conway's Law, supports domain-driven design, and matches enterprise architecture best practices.  
**Status**: Implemented (see directory structure)  
**Consequence**: Requires cross-domain communication mechanisms (APIs/events) but provides clear ownership boundaries.

### 7.2 Communication Mechanism Decision
**Decision**: Hybrid approach - synchronous REST/gRPC for immediate consistency needs, asynchronous event-driven (Kafka) for eventual consistency and loose coupling.  
**Rationale**: Balances performance requirements with scalability and fault tolerance. Critical user-facing operations use sync; background processes, analytics, and notifications use async.  
**Status**: Framework established (contracts in `shared/contracts/`, events in `shared/events/`)  
**Consequence**: Requires clear sync/async boundaries but provides appropriate consistency models for different use cases.

### 7.3 Data Ownership Decision
**Decision**: Each service owns its primary storage; no direct cross-service database access.  
**Rationale**: Ensures loose coupling, independent deployability, and clear responsibility boundaries.  
**Status**: Pattern established for migrated services; to be enforced for all new services  
**Implementation**: Services use dedicated database schemas or separate instances; cross-domain reads via API or event replay.

### 7.4 Technology Stack Decision
**Decision**: Standardize on Python/FastAPI for services, PostgreSQL for relational data, MongoDB for document/KB, Neo4j for graph, Kafka for events.  
**Rationale**: Matches team expertise, provides appropriate tool for each data type, proven in production at scale.  
**Status**: Used in migrated services; standard for new service generation  
**Consequence**: Technology standardization reduces cognitive overhead and enables knowledge sharing.

### 7.5 Migration Approach Decision
**Decision**: Strangler fig pattern with domain-by-domain cutover, maintaining backward compatibility.  
**Rationale**: Minimizes risk, allows learning and adjustment, enables business value delivery throughout transition.  
**Status**: Phase 0 validates approach; Phase 1 executes first domain migrations  
**Consequence**: Requires careful cutover planning but provides risk mitigation and value realization throughout.

## 8. Risks and Mitigations
Identified risks and their mitigation strategies:

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Service Coupling Accidentally Introduced** | Medium-High | Medium | Enforce dependency direction rules (services → shared only); architecture reviews; dependency analysis in CI |
| **Data Migration Complexity** | High | Low-Medium | Invest in CDC tooling early; dual-write patterns; comprehensive validation scripts; phased migration |
| **Observability Gaps** | Medium | Medium | Implement shared observability library first; mandate instrumentation in service template; centralized dashboard |
| **Performance Regression During Migration** | Medium | Low | Canary deployments; performance baseline testing; gradual traffic shift; rollback procedures |
| **Team Skill Gaps** | Medium | Low-Medium | Pair programming; internal tech talks; documentation; hiring/upskilling plan |
| **Scope Creep in Domain Boundaries** | Low | Medium | Clear domain definitions; architecture review board; backlog grooming with domain owners |
| **Event Schema Drift** | Medium | Low | Schema Registry enforcement; backward/forward compatibility requirements; automated compatibility testing |
| **Underestimating Cutover Complexity** | Medium | Medium | Detailed cutover playbooks; runbook automation; failure injection testing; stakeholder communication plan |
| **Security Gaps in New Services** | High | Low | Security templates in service scaffolding; automated security scanning; penetration testing schedule; centralized auth/z |

## Appendices

### Appendix A: Glossary
- **QEOS**: Quality Engineering Operating System - see Architecture Blueprint v1.0 for definition
- **QIP**: Quality Intelligence Platform - see Architecture Blueprint v1.0 for definition
- **CDC**: Change Data Capture
- **RTO/RPO**: Recovery Time Objective / Recovery Point Objective
- **MTTD/MTTR**: Mean Time To Detect / Mean Time To Respond
- **SLA**: Service Level Agreement
- **ADR**: Architecture Decision Record

### Appendix B: Reference Architecture
See Architecture Blueprint v1.0 for reference architecture diagrams including:
- C4 Container view of the target architecture
- Domain interaction patterns (sync vs async)
- Deployment architecture with Kubernetes
- Data flow layers (operational → event store → data lake → warehouse → ML)
- Event-driven choreography examples

### Appendix C: Migration Playbook Outline
(Summary of cutover procedures for each service type)
## 8. What Actually Shipped (2026-09/10 reality checkpoint)

The migration paths above predate delivery. As of 2026-10-02 the running
platform is: auth-service (SSO, TOTP MFA, httpOnly refresh cookie, rotation +
replay detection), organization-service, project-service, ingestion-service
(collect API, PII masking, retention, analytics incl. 90-day flaky windows
from daily rollups, mute, branches, code-change data), qeos-collector
(incl. Surefire rerun-attempt expansion and git diff data), NGINX gateway,
React dashboard, retention + analytics-rollup jobs — PostgreSQL-only,
docker-compose, CI with a 70+-check full-stack smoke. TODO.md is the live
record; IMPLEMENTATION_PLAN.md the forward plan; the blueprint's
Implementation Status banner maps current vs target.

`execution/`, `automation/`, `marketplace/`, `collaboration/`,
`intelligence/`, `platforms/qip-service` remain unwired prototypes from the
earlier blueprint-first attempt (each now carries an UNWIRED PROTOTYPE
README). The TODO-driven slice approach shipped; the prototype-first approach
did not — new target slices follow the blueprint's adoption triggers instead.
