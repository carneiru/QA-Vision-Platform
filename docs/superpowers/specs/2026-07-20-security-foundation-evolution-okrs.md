# OKRs – QA Vision Platform Security Foundation Evolution
## Program: 24-Week Transformation (Jul 2026 – Dec 2026)

---

## OKR Framework

| Symbol | Meaning |
|--------|---------|
| **O** | Objective — Qualitative, ambitious, time-bound |
| **KR** | Key Result — Quantitative, measurable, verifiable |
| **🟢/🟡/🔴** | On Track / At Risk / Off Track (weekly assessment) |

---

## Program-Level OKRs

### O1: Deliver Production-Grade Zero-Trust Security Platform
*Transform fragmented tooling into cohesive platform meeting all 16 architectural objectives*

| KR | Target | Measurement | Owner | Status |
|----|--------|-------------|-------|--------|
| **KR1.1** | 100% workloads on SPIFFE identity (X.509 1h + JWT 5m) | SPIRE API `WorkloadIdentity` CR status | Platform Lead | 🔴 Not Started |
| **KR1.2** | 100% inter-service traffic mTLS STRICT | Istio `PeerAuthentication` mode + `DestinationRule` TLSSettings | Platform Lead | 🔴 Not Started |
| **KR1.3** | 100% pods covered by CiliumNetworkPolicy (default-deny) | Cilium `NetworkPolicy` enforcement status | Platform Lead | 🔴 Not Started |
| **KR1.4** | 100% production images signed, SLSA L3, SBOM | Cosign verify + SLSA provenance + Syft SBOM in admission | Security Lead | 🔴 Not Started |
| **KR1.5** | <100ms p99 API latency, <30s threat detection→alert | Prometheus histograms + Alertmanager latency | SRE Lead | 🔴 Not Started |

### O2: Achieve Measurable Security Posture Improvement
*Quantify risk reduction through automated scoring and continuous assessment*

| KR | Target | Measurement | Owner | Status |
|----|--------|-------------|-------|--------|
| **KR2.1** | Security Scorecard operational (daily calculation, 40+ metrics) | `SecurityScorecardDefinition` CR + PromQL metrics pipeline | Security Lead | 🔴 Not Started |
| **KR2.2** | ≥85% compliance evidence automated (SOC2, PCI, HIPAA, NIST) | Audit API evidence coverage report | Compliance Officer | 🔴 Not Started |
| **KR2.3** | FAIR risk model calibrated, executive dashboard live | Risk metrics API `/api/v1/analytics/risk-metrics` | Security Lead | 🔴 Not Started |
| **KR2.4** | Red team exercise: 0 critical findings, ≤5 high | Red team report + remediation tracker | Security Lead | 🔴 Not Started |
| **KR2.5** | Threat models as code for 100% critical services | `ThreatModel` CR coverage in GitOps repo | Security Architect | 🔴 Not Started |

### O3: Enable Developer Velocity Through Security Platform APIs
*Self-service security capabilities reducing onboarding from weeks to minutes*

| KR | Target | Measurement | Owner | Status |
|----|--------|-------------|-------|--------|
| **KR3.1** | <5 min to onboard new service (identity, policy, certs, runtime) | Platform API timing + developer survey | Platform Lead | 🔴 Not Started |
| **KR3.2** | 100% API surface covered by OpenAPI 3.1 + SDKs (Go/Python/TS) | Spec validation + SDK publish status | Platform Lead | 🔴 Not Started |
| **KR3.3** | Zero-downtime migration: legacy APIs fully deprecated by Week 24 | Shim layer traffic % → 0 | Platform Lead | 🔴 Not Started |
| **KR3.4** | GitOps drift detection <5 min, auto-remediation >90% | ArgoCD drift alerts + remediation rate | SRE Lead | 🔴 Not Started |
| **KR3.5** | Developer NPS for security platform ≥ 40 | Quarterly survey | Engineering Lead | 🔴 Not Started |

### O4: Build High-Performing Security Platform Team
*Team capability, knowledge retention, and operational excellence*

| KR | Target | Measurement | Owner | Status |
|----|--------|-------------|-------|--------|
| **KR4.1** | All 6 engineers certified (CKA + domain cert) by Week 8 | Certification tracker | Engineering Lead | 🔴 Not Started |
| **KR4.2** | 20 P0 runbooks documented, tested, owned | Runbook registry + drill results | SRE Lead | 🔴 Not Started |
| **KR4.3** | SPIRE DR drill: CA rotation <5 min, zero workload disruption | Drill report + metrics | SRE Lead | 🔴 Not Started |
| **KR4.4** | Load test at 2× peak passes all SLOs | Load test report (k6/Gatling) | SRE Lead | 🔴 Not Started |
| **KR4.5** | Team engagement score ≥ 4.5/5 (quarterly pulse) | Survey | Engineering Lead | 🔴 Not Started |

---

## Phase-Level OKRs

### Phase 1 (Weeks 1-4): Identity Foundation

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O1.1: Deploy SPIRE as Identity Foundation** | KR1: 3 SPIRE clusters HA (prod/staging/dev) <br> KR2: 100% test workloads getting SVIDs <br> KR3: Federation trust domains established <br> KR4: CSI driver + SDS operational | Platform Lead |
| **O1.2: Integrate Human Identity Providers** | KR1: Keycloak adapter production-ready <br> KR2: Entra ID + Okta adapters implemented <br> KR3: MFA Configuration CRD functional <br> KR4: SCIM provisioning working for 2 IdPs | Platform Lead |
| **O1.3: Establish WorkloadIdentity CRD + Controller** | KR1: CRD v1beta1 published, conversion webhook <br> KR2: Controller reconciles <5s p99 <br> KR3: Identity APIs L1 gates passing <br> KR4: Documentation + examples complete | Platform Lead |

**Phase 1 Gate**: All L1 gates (1.1-1.8) passing, SPIRE HA validated, attestation working

---

### Phase 2 (Weeks 5-8): Control Plane + Secrets

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O2.1: Deploy Security Control Plane** | KR1: API Server (gRPC/REST) HA, <50ms p99 <br> KR2: etcd cluster (3 AZ) operational <br> KR3: NATS JetStream for event bus <br> KR4: Reconcile engine processing <100ms p99 | Platform Lead |
| **O2.2: Implement Secrets Management** | KR1: Secret CRD + Controller managing Vault <br> KR2: RotationPolicy CRD with canary + grace period <br> KR3: Dual-write to legacy Vault operational <br> KR4: Audit log unified, queryable via API | Platform Lead |
| **O2.3: Security Domain Hierarchy** | KR1: SecurityDomain CRD (Domain→Namespace→App) <br> KR2: Vault namespace mapping automated <br> KR3: SaaS/Multi-cloud/Air-gapped domain types <br> KR4: Domain controller reconciles drift <5min | Platform Lead |

**Phase 2 Gate**: L1 gates (2.1-2.8) passing, CP HA tested, dual-write verified

---

### Phase 3 (Weeks 9-12): Certificates + Service Mesh

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O3.1: SPIRE as Certificate Authority** | KR1: SPIRE Issuer for cert-manager operational <br> KR2: Auto-renewal + CT logging enabled <br> KR3: Private key rotation on renewal <br> KR4: Certificate CRD L1 gates passing | Platform Lead |
| **O3.2: Istio STRICT mTLS Rollout** | KR1: PERMISSIVE → STRICT in 4-week progression <br> KR2: 100% namespaces opted-in, zero breakage <br> KR3: AuthorizationPolicy default-deny enforced <br> KR4: SDS integration with SPIRE validated | Platform Lead |
| **O3.3: Certificate + Policy CRDs** | KR1: Certificate CRD with renewal status <br> KR2: Policy CRD (Istio + Cilium unified) <br> KR3: Policy controller reconciliation <5s <br> KR4: `istioctl analyze` clean | Platform Lead |

**Phase 3 Gate**: L1 gates (3.1-3.8) passing, mTLS 100% STRICT, AuthZ no bypass

---

### Phase 4 (Weeks 13-16): Network + Runtime Security

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O4.1: Cilium Zero-Trust Networking** | KR1: Cilium CNI migrated (dual CNI → full) <br> KR2: ClusterMesh + WireGuard operational <br> KR3: Egress Gateway + DNS Policy enforced <br> KR4: L7 policies (HTTP/Kafka/gRPC) working | Platform Lead |
| **O4.2: Runtime Security (Falco + Tetragon)** | KR1: Falco DaemonSet + Tetragon DaemonSet <br> KR2: MITRE ATT&CK tagging on all rules <br> KR3: Correlation engine dedup >90% <br> KR4: Auto-response (isolate/kill/block) tested | Security Lead |
| **O4.3: Network + Runtime Policy CRDs** | KR1: RuntimePolicy CRD with response actions <br> KR2: CiliumNetworkPolicy CRD integrated <br> KR3: L1 gates (4.1-4.10) passing <br> KR4: FP rate <5% after 4 weeks 15-16 | Security Lead |

**Phase 4 Gate**: L1 gates (4.1-4.10) passing, default-deny enforced, FP <5%

---

### Phase 5 (Weeks 17-20): Supply Chain + Observability

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O5.1: SLSA L3 Supply Chain** | KR1: Tekton pipeline hermetic, reproducible <br> KR2: Cosign keyless signing + Rekor transparency <br> KR3: SBOM (SPDX + CycloneDX) on every build <br> KR4: Kyverno admission enforcing verify + provenance | Security Lead |
| **O5.2: Unified Observability Stack** | KR1: Thanos (metrics) + Loki (logs) + Tempo (traces) <br> KR2: 5 Security dashboards (Identity, Network, Runtime, Supply Chain, Compliance) <br> KR3: Exemplars + correlation IDs working <br> KR4: SLO-based alerting (Burn rate, Multi-window) | SRE Lead |
| **O5.3: Supply Chain + Analytics APIs** | KR1: SBOM API queryable by component/version <br> KR2: Verify API for admission decisions <br> KR3: Analytics API trends + risk metrics <br> KR4: L1 gates (5.1-5.11) passing | Security Lead |

**Phase 5 Gate**: L1 gates (5.1-5.11) passing, SLSA L3 verified, unsigned deploy blocked

---

### Phase 6 (Weeks 21-24): Governance + APIs + Decommission

| Objective | Key Results | Owner |
|-----------|-------------|-------|
| **O6.1: Threat Modeling as Code** | KR1: ThreatModel CRD (STRIDE/PASTA/Attack Trees) <br> KR2: Controller generates test cases from models <br> KR3: MITRE ATT&CK mapping automated <br> KR4: Residual risk scored via FAIR | Security Architect |
| **O6.2: Security Scorecards + Risk** | KR1: 8 categories, 40+ metrics, weighted <br> KR2: Daily calculation, trend API <br> KR3: FAIR risk engine calibrated <br> KR4: Executive dashboard (Grafana) live | Security Lead |
| **O6.3: Platform APIs + SDKs** | KR1: OpenAPI 3.1 (14 groups, 100+ endpoints) <br> KR2: Go/Python/TS SDKs published <br> KR3: JWT/API Key auth, rate limiting <br> KR4: Legacy shim traffic = 0% | Platform Lead |
| **O6.4: Legacy Decommission** | KR1: Vault legacy sealed, secrets migrated <br> KR2: Kong shared → per-env complete <br> KR3: OPA → Kyverno migration done <br> KR4: cert-manager → SPIRE issuer only | Platform Lead |

**Phase 6 Gate (Launch)**: All L1 gates (6.1-6.9) passing, API contract stable, runbooks complete

---

## Weekly Tracking Cadence

### Monday: Planning & Priorities
- Review previous week OKR progress
- Set weekly priorities aligned to Phase KRs
- Identify blockers needing escalation

### Wednesday: Mid-Week Check
- Quick sync on at-risk KRs
- Resource reallocation if needed
- Cross-team dependency resolution

### Friday: Retrospective & Confidence
- Update OKR confidence (🟢/🟡/🔴)
- Document learnings
- Update tracking dashboard

### Phase Gate Reviews (End of Weeks 4, 8, 12, 16, 20, 24)
| Attendees | Duration | Artifacts |
|-----------|----------|-----------|
| Steering Committee + Leads | 2 hours | Phase Gate Report, Risk Register, Go/No-Go |

---

## OKR Scoring

| Score | Label | Criteria |
|-------|-------|----------|
| **1.0** | **Achieved** | All KRs met or exceeded |
| **0.7 - 0.9** | **Substantial** | Most KRs met, minor gaps |
| **0.4 - 0.6** | **Partial** | Some KRs met, significant gaps |
| **0.1 - 0.3** | **Minimal** | Few KRs met, major gaps |
| **0.0** | **Failed** | No KRs met |

**Program Success Threshold**: Average score ≥ 0.7 across all 4 Objectives

---

## Risk-Adjusted OKRs (Contingency)

| Risk | If Materialized | Adjusted Target |
|------|-----------------|-----------------|
| Timeline slip >4 weeks | Extend Phase 5-6 by 2 weeks each | KR1.4 → 90% images signed, KR2.4 → Red team Week 28 |
| Team attrition (>1 engineer) | Reduce scope: defer ThreatModel CRD test gen | KR6.1 → Manual test case generation |
| SPIRE bootstrap failure >Week 4 | Fallback: K8s SA tokens + SPIRE sidecar | KR1.1 → Hybrid identity Week 8 |
| Cilium kernel incompatibility | Use fallback CNI + Cilium L7 only | KR1.3 → 80% coverage L3/L4 + 100% L7 |
| Vendor support gaps | Self-support with community + runbooks | KR4.1 → Internal certifications only |

---

## Dashboard & Reporting

### Grafana Dashboard: `security-platform-okrs`
- **Real-time**: KR metrics (PromQL queries)
- **Weekly**: Confidence trends, velocity
- **Phase Gate**: Go/No-Go criteria status

### Weekly Status Report (Friday EOD)
```
## Week X Status – Phase Y

### Objective Progress
O1: ████████░░ 80% (KR1.1 🟢, KR1.2 🟡, KR1.3 🔴, KR1.4 🔴, KR1.5 🟢)
O2: ██████░░░░ 60% (KR2.1 🟢, KR2.2 🟡, KR2.3 🔴, KR2.4 🔴, KR2.5 🔴)
O3: ████░░░░░░ 40% (KR3.1 🟢, KR3.2 🟡, KR3.3 🔴, KR3.4 🟢, KR3.5 —)
O4: ███████░░░ 70% (KR4.1 🟢, KR4.2 🟡, KR4.3 🔴, KR4.4 🔴, KR4.5 🟢)

### Top 3 Risks
1. [Risk] → [Mitigation] → [Owner] → [Due]
2. [Risk] → [Mitigation] → [Owner] → [Due]
3. [Risk] → [Mitigation] → [Owner] → [Due]

### Decisions Needed
- [Decision] → [Options] → [Recommendation] → [Approver]
```

### Monthly Executive Summary (1st Monday)
- Program health (OKR scores, budget, timeline)
- Strategic risks & decisions
- Next 30-day priorities
- Resource asks

---

*Version: 1.0 | Owner: Engineering Lead | Review: Weekly | Approved: VP Engineering + CISO*