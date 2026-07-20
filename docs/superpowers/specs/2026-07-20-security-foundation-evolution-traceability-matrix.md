# Traceability Matrix
## QA Vision Platform – Security Foundation Evolution

---

## Overview

This matrix provides bidirectional traceability between:
- **Requirements** (from original 16 objectives)
- **ADRs** (Architecture Decision Records)
- **Components** (Systems, APIs, CRDs, Operators)
- **Validation Checks** (L1-L4 from validation checklist)
- **Risks** (From risk analysis)
- **Migration Phases** (6 phases, 24 weeks)

---

## Requirements ↔ ADRs ↔ Components

| Req ID | Requirement | ADR(s) | Component(s) | API Endpoints |
|--------|-------------|--------|--------------|---------------|
| **REQ-01** | Domain-Driven Design for Security Domain | ADR-001 | Identity Context, Access Context, Protection Context, Secrets Context, Certificates Context, Compliance Context | `/api/v1/identity/*`, `/api/v1/secrets/*`, `/api/v1/certificates/*`, `/api/v1/policies/*`, `/api/v1/runtime/*`, `/api/v1/compliance/*` |
| **REQ-02** | Security Control Plane | ADR-002 | Control Plane API (gRPC/REST), Reconcile Engine, State Store (etcd), Event Bus (NATS), Operators (6x) | `/api/v1/*` (all), gRPC: `SecurityControlPlane` service |
| **REQ-03** | Dedicated Kong per Environment | ADR-003 | Kong Gateway (prod/staging/dev), Kong Operator, ArgoCD Apps | Kong Admin API (internal) |
| **REQ-04** | Service Mesh (Istio, mTLS STRICT, AuthZ) | ADR-004 | Istio Control Plane, PeerAuthentication, AuthorizationPolicy, RequestAuthentication, SDS | Istio APIs (internal) |
| **REQ-05** | SPIFFE/SPIRE Workload Identity | ADR-005 | SPIRE Server (3x), SPIRE Agent (DaemonSet), CSI Driver, WorkloadIdentity CRD | `/api/v1/identity/workloads`, `/api/v1/identity/federations` |
| **REQ-06** | Identity Abstraction Layer | ADR-006 | IdentityProvider interface, KeycloakAdapter, EntraIDAdapter, OktaAdapter, Auth0Adapter, PingAdapter, SCIM Provisioner | `/api/v1/identity/humans`, `/api/v1/identity/mfa` |
| **REQ-07** | Security Domains (Hierarchical Vault) | ADR-007 | SecurityDomain CRD, Domain Controller, Vault Namespaces, Secret CRD | `/api/v1/secrets/*`, `/api/v1/secrets/rotation-policies` |
| **REQ-08** | Runtime Security (Falco + Tetragon) | ADR-008 | Falco (DaemonSet), Tetragon (DaemonSet), Correlation Engine, RuntimePolicy CRD, Response Actions | `/api/v1/runtime/threats`, `/api/v1/runtime/response-actions`, `/api/v1/runtime/policies` |
| **REQ-09** | Supply Chain Security (SLSA L3, Sigstore, SBOM) | ADR-009 | Tekton Pipeline, Cosign Keyless, Rekor, SBOM Generator, Kyverno Admission Policy, SupplyChainPolicy CRD | `/api/v1/supply-chain/sbom/*`, `/api/v1/supply-chain/verify/*`, `/api/v1/supply-chain/policies` |
| **REQ-10** | Zero Trust Networking (Cilium) | ADR-010 | Cilium CNI, CiliumNetworkPolicy, ClusterMesh, WireGuard, Egress Gateway, DNS Policy, AuthRequired | Cilium APIs (internal) |
| **REQ-11** | Security Observability Stack | ADR-011 | Prometheus/Thanos, Loki, Tempo, Grafana (5 dashboards), Alertmanager | `/api/v1/analytics/*` |
| **REQ-12** | Threat Modeling (STRIDE + PASTA + Attack Trees) | ADR-012 | ThreatModel CRD, Threat Model Controller, MITRE Mapper, Test Case Generator | `/api/v1/threats/models`, `/api/v1/threats/attack-trees` |
| **REQ-13** | Security Scorecards (8 categories, 40+ metrics) | ADR-013 | SecurityScorecardDefinition CRD, Scorecard Calculator, PromQL Metrics, FAIR Risk Engine | `/api/v1/analytics/security-scorecard`, `/api/v1/analytics/risk-metrics`, `/api/v1/analytics/trends` |
| **REQ-14** | Security Platform APIs (OpenAPI 3.1) | ADR-014 | API Gateway, OpenAPI Spec (14 groups, 100+ endpoints), SDKs (Go/Python/TS) | All `/api/v1/*` endpoints |
| **REQ-15** | Backward Compatibility | ADR-015 | API Shim Layer, Dual-Write Controller, Feature Flags, Migration Jobs | Shim: `/api/v0/*` (legacy) |
| **REQ-16** | Multi-Environment GitOps | ADR-016 | ArgoCD App-of-Apps, SealedSecrets, External Secrets Operator, Environment Promotion Pipeline | ArgoCD API (internal) |

---

## Requirements ↔ Validation Checks

| Req ID | L1 Automated Gates | L2 Manual Verification | L3 Security Review | L4 Stakeholder Acceptance |
|--------|-------------------|----------------------|-------------------|--------------------------|
| REQ-01 | 1.1-1.8 | 1.9-1.14 | 1.15-1.18 | 1.19-1.21 |
| REQ-02 | 2.1-2.8 | 2.9-2.15 | 2.16-2.20 | 2.21-2.23 |
| REQ-03 | 3.1-3.8 | 3.9-3.16 | 3.17-3.20 | 3.21-3.23 |
| REQ-04 | 4.1-4.10 | 4.11-4.20 | 4.21-4.24 | 4.25-4.27 |
| REQ-05 | 5.1-5.11 | 5.12-5.22 | 5.23-5.26 | 5.27-5.29 |
| REQ-06 | 6.1-6.9 | 6.10-6.26 | 6.27-6.30 | 6.31-6.35 |
| REQ-07 | (covered in REQ-01/02) | | | |
| REQ-08 | (covered in Phase 4) | | | |
| REQ-09 | (covered in Phase 5) | | | |
| REQ-10 | (covered in Phase 4) | | | |
| REQ-11 | (covered in Phase 5) | | | |
| REQ-12 | (covered in Phase 6) | | | |
| REQ-13 | (covered in Phase 6) | | | |
| REQ-14 | (covered in Phase 6) | | | |
| REQ-15 | (covered in all phases) | | | |
| REQ-16 | (covered in all phases) | | | |

---

## Components ↔ Risks

| Component | Risk IDs | Mitigation Status |
|-----------|----------|------------------|
| SPIRE Server/agent | TR-01, TR-04, SR-02, Risk#1 | C1: DR drill Wk22 |
| Control Plane (API, etcd, NATS) | TR-04, TR-02, SR-01, Risk#6 | L1: 2.1-2.8, C5: Load test |
| Istio (mTLS, AuthZ) | TR-03, SR-04, Risk#2 | Phase 3 gradual rollout |
| Cilium (CNI, eBPF) | TR-02, TR-05, SR-05, Risk#3 | Canary + kernel gate |
| Falco/Tetragon | OR-02, SR-01, Risk#4 | 8-week tuning, correlation |
| Tekton/SLSA Pipeline | TR-06, SR-03, Risk#5 | Isolated build clusters |
| Security Scorecard | SR-01, Risk#9 | Gaming resistance test (6.29) |
| API Gateway | SR-01, Risk#10 | OWASP API Top 10 (6.27) |
| Team | OR-01, BR-04, Risk#9 | Training Wk18-22, Cert Wk22 |

---

## ADRs ↔ Migration Phases

| ADR | Phase | Week Range | Dependencies |
|-----|-------|------------|--------------|
| ADR-001 (DDD) | 1 | 1-4 | None (foundational) |
| ADR-002 (Control Plane) | 2 | 5-8 | ADR-001 (contexts) |
| ADR-003 (Per-Env Kong) | 2-3 | 5-12 | ADR-002 (CP for config) |
| ADR-004 (Istio) | 3 | 9-12 | ADR-005 (SPIRE for SDS) |
| ADR-005 (SPIRE) | 1 | 1-4 | ADR-001 (Identity Context) |
| ADR-006 (IdP Abstraction) | 1 | 1-4 | ADR-001, ADR-005 |
| ADR-007 (Security Domains) | 2 | 5-8 | ADR-002, ADR-005 |
| ADR-008 (Runtime Security) | 4 | 13-16 | ADR-004, ADR-010, ADR-011 |
| ADR-009 (Supply Chain) | 5 | 17-20 | ADR-002, ADR-011 |
| ADR-010 (Cilium) | 4 | 13-16 | ADR-005 (identity) |
| ADR-011 (Observability) | 5 | 17-20 | All (data sources) |
| ADR-012 (Threat Modeling) | 6 | 21-24 | ADR-001, ADR-008, ADR-009 |
| ADR-013 (Scorecards) | 6 | 21-24 | ADR-011 (metrics) |
| ADR-014 (APIs) | 6 | 21-24 | All (API facade) |
| ADR-015 (Compatibility) | All | 1-24 | All (shim layer) |
| ADR-016 (GitOps) | All | 1-24 | Infra provisioned |

---

## Validation Checks ↔ Migration Phases

| Phase | L1 Gates | L2 Verification | L3 Security Review | L4 Acceptance |
|-------|----------|-----------------|-------------------|---------------|
| **Phase 1** (Wk 1-4) | 1.1-1.8 | 1.9-1.14 | 1.15-1.18 | 1.19-1.21 |
| **Phase 2** (Wk 5-8) | 2.1-2.8 | 2.9-2.15 | 2.16-2.20 | 2.21-2.23 |
| **Phase 3** (Wk 9-12) | 3.1-3.8 | 3.9-3.16 | 3.17-3.20 | 3.21-3.23 |
| **Phase 4** (Wk 13-16) | 4.1-4.10 | 4.11-4.20 | 4.21-4.24 | 4.25-4.27 |
| **Phase 5** (Wk 17-20) | 5.1-5.11 | 5.12-5.22 | 5.23-5.26 | 5.27-5.29 |
| **Phase 6** (Wk 21-24) | 6.1-6.9 | 6.10-6.26 | 6.27-6.30 | 6.31-6.35 |

---

## Phase Gates (Go/No-Go Criteria)

| Phase | Must Pass (All) | Should Pass (All) | Blockers if Failed |
|-------|-----------------|-------------------|-------------------|
| **Phase 1** | 1.1-1.8, 1.15-1.18 | 1.9-1.14 | SPIRE not HA, attestation failing |
| **Phase 2** | 2.1-2.8, 2.16-2.20 | 2.9-2.15 | CP not HA, dual-write broken |
| **Phase 3** | 3.1-3.8, 3.17-3.20 | 3.9-3.16 | mTLS <100%, AuthZ bypass |
| **Phase 4** | 4.1-4.10, 4.21-4.24 | 4.11-4.20 | Default-deny broken, FP >5% |
| **Phase 5** | 5.1-5.11, 5.23-5.26 | 5.12-5.22 | SLSA <L3, unsigned deploy |
| **Phase 6** | 6.1-6.9, 6.27-6.30 | 6.10-6.26 | API contract break, runbooks |

---

## CRD Inventory ↔ Requirements

| CRD | API Group | Requirement | Controller | Validation |
|-----|-----------|-------------|------------|------------|
| WorkloadIdentity | security.qa-vision.io/v1 | REQ-01, REQ-05 | Identity Controller | 1.3, 1.10, 1.11 |
| Federation | security.qa-vision.io/v1 | REQ-05 | Federation Controller | 1.5, 1.12 |
| HumanIdentity | security.qa-vision.io/v1 | REQ-06 | Human Identity Controller | 1.6, 1.13 |
| MFAConfiguration | security.qa-vision.io/v1 | REQ-06 | MFA Controller | 1.14 |
| Secret | security.qa-vision.io/v1 | REQ-07 | Secrets Controller | 2.4, 2.5, 2.9-2.11 |
| SecretRotationPolicy | security.qa-vision.io/v1 | REQ-07 | Rotation Controller | 2.10, 2.11 |
| Certificate | security.qa-vision.io/v1 | REQ-04, REQ-05 | Certificate Controller | 3.1, 3.2, 3.9 |
| Policy | security.qa-vision.io/v1 | REQ-01, REQ-04 | Policy Controller | 3.5, 3.11, 3.12 |
| ThreatModel | security.qa-vision.io/v1 | REQ-12 | Threat Model Controller | 6.1, 6.2, 6.10, 6.11 |
| SecurityScorecardDefinition | security.qa-vision.io/v1 | REQ-13 | Scorecard Controller | 6.3, 6.4, 6.12-6.14 |
| RuntimePolicy | security.qa-vision.io/v1 | REQ-08 | Runtime Controller | 4.10, 4.17, 4.18 |
| SupplyChainPolicy | security.qa-vision.io/v1 | REQ-09 | Supply Chain Controller | 5.5, 5.6, 5.13 |
| CiliumNetworkPolicy | cilium.io/v2 | REQ-10 | Cilium Operator | 4.3, 4.4, 4.12 |
| AuthorizationPolicy | security.istio.io/v1 | REQ-04 | Istio Pilot | 3.5, 3.11 |
| PeerAuthentication | security.istio.io/v1 | REQ-04 | Istio Pilot | 3.4, 3.16 |

---

## API Endpoint Coverage

| API Group | Endpoints | Requirement | Test Coverage |
|-----------|-----------|-------------|--------------|
| Identity | 18 | REQ-05, REQ-06 | 6.16 |
| Secrets | 22 | REQ-07 | 6.17 |
| Certificates | 12 | REQ-04, REQ-05 | 6.18 |
| Policies | 15 | REQ-01, REQ-04 | 6.19 |
| Runtime | 14 | REQ-08 | 6.20 |
| Compliance | 10 | REQ-01 | 6.21 |
| Audit | 8 (incl. SSE) | REQ-02 | 6.22 |
| Supply Chain | 12 | REQ-09 | 6.23 |
| Analytics | 10 | REQ-11, REQ-13 | 6.24 |
| **Total** | **121** | | |

---

## Risk Coverage by Validation

| Risk Category | Validation Checks | Residual Risk |
|---------------|------------------|---------------|
| Technical (TR-01 to TR-07) | All Phase L1+L2 | 5/7 Medium, 2/7 Low |
| Operational (OR-01 to OR-05) | L2+L3+L4, Team certs | 3/5 Medium, 2/5 Low |
| Security (SR-01 to SR-05) | L3 Security Reviews | 2/5 Medium, 3/5 Low |
| Compliance (CR-01 to CR-03) | L3+L4, Compliance sign-off | 2/3 Low |
| Business (BR-01 to BR-04) | L4, Phase gates | 2/4 Medium, 2/4 Low |

---

## Change Impact Analysis

| Change | Affected Requirements | Affected ADRs | Affected Components | Validation Re-run |
|--------|---------------------|---------------|---------------------|-------------------|
| SPIRE → SPIRE Controller Manager | REQ-05 | ADR-005 | SPIRE Server, Agent, CSI, WorkloadIdentity CRD | Phase 1 L1-L4 |
| Istio → Ambient Mesh | REQ-04 | ADR-004 | Istio CP, Sidecars, AuthZ, SDS | Phase 3 L1-L4 |
| Vault → External Secrets Only | REQ-07 | ADR-007 | SecurityDomain, Secret CRD, Shim | Phase 2 L1-L4 |
| Thanos → Mimir | REQ-11 | ADR-011 | Prometheus, Grafana, Alerting | Phase 5 L1-L4 |
| Kyverno → OPA Gatekeeper | REQ-09 | ADR-009 | Admission Policy, SupplyChainPolicy | Phase 5 L1-L4 |

---

## Compliance Control Mapping

| Framework | Control | Implemented By | Evidence Source | Automation |
|-----------|---------|----------------|-----------------|------------|
| SOC2 CC6.1 | Logical access | SPIRE, Istio mTLS, Cilium | Audit API, NetPol status | 100% |
| SOC2 CC6.7 | Data transmission | Istio STRICT, WireGuard | mTLS verification, Cilium encryption | 100% |
| PCI-DSS 3.4 | Encrypt transmission | Same as above | Same | 100% |
| PCI-DSS 8.3 | MFA | Identity Abstraction + MFA | MFA status API | 100% |
| HIPAA 164.312(a) | Access control | SPIFFE, AuthZ Policies | WorkloadIdentity, Policy eval | 100% |
| HIPAA 164.312(e) | Transmission security | mTLS everywhere | Same as SOC2 | 100% |
| GDPR Art. 32 | Security of processing | Full stack | Scorecard + Risk metrics | 85% |
| NIST IA-2 | Identification/authentication | SPIRE + IdP | Identity APIs | 100% |
| NIST SC-7 | Boundary protection | Cilium, Istio, Kong | Network policy status | 100% |
| NIST SI-4 | Monitoring | Falco, Tetragon, Scorecard | Threat events, Metrics | 95% |

---

## Glossary of IDs

| Prefix | Meaning |
|--------|---------|
| REQ-XX | Original requirement (1-16) |
| ADR-XXX | Architecture Decision Record |
| TR-XX | Technical Risk |
| OR-XX | Operational Risk |
| SR-XX | Security Risk |
| CR-XX | Compliance Risk |
| BR-XX | Business Risk |
| L1-L4 | Validation Level (Automated → Stakeholder) |
| C1-C9 | Launch Conditions (P0/P1) |
| Wk XX | Week number in 24-week plan |