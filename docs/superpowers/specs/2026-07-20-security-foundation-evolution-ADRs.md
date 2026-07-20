# Architecture Decision Records (ADRs)
## QA Vision Platform – Security Foundation Evolution

---

## ADR-001: Domain-Driven Design for Security Domain

**Status**: Accepted
**Date**: 2026-07-20
**Deciders**: Security Architecture Team

### Context
The original security foundation treated security as a cross-cutting concern with disparate tools (Vault, Kong, OPA, cert-manager) operating independently. This led to operational silos, inconsistent policies, and difficulty reasoning about security posture holistically.

### Decision
Adopt Domain-Driven Design (DDD) for the security domain with the following bounded contexts:

1. **Identity Context** – Workload identities (SPIFFE/SPIRE), human identities (IdP federation), MFA
2. **Access Context** – Policies (OPA/Kyverno), network policies (Cilium), service mesh auth (Istio)
3. **Protection Context** – Runtime security (Falco/Tetragon), threat detection, response automation
4. **Secrets Context** – Dynamic/static secrets, rotation, audit, encryption
5. **Certificates Context** – PKI management, SPIRE integration, certificate lifecycle
6. **Compliance Context** – Frameworks mapping, evidence collection, assessments

### Consequences
- **Positive**: Clear ownership, independent evolution, explicit contracts between contexts
- **Negative**: Initial complexity in defining context boundaries, requires context mapping
- **Neutral**: Need for anti-corruption layers at context boundaries

### Implementation
- Each context gets its own Kubernetes operator/controller
- Shared kernel: Security Control Plane gRPC API
- Context communication via async events (Kafka/NATS)

---

## ADR-002: Security Control Plane as Central Orchestration

**Status**: Accepted
**Date**: 2026-07-20

### Context
Multiple security tools needed coordination: policy distribution, secret rotation triggers, certificate renewal, threat response actions. Point-to-point integrations created tight coupling.

### Decision
Implement a dedicated Security Control Plane with:
- **API Gateway**: gRPC/REST facade for all security operations
- **Reconcile Engine**: Kubernetes controller pattern for desired state enforcement
- **State Store**: etcd-backed with CRDT for distributed consistency
- **Event Bus**: NATS JetStream for async event propagation
- **Operators**: Per-domain controllers (Identity, Secrets, Certificates, Policies, Runtime, Compliance)

### Consequences
- **Positive**: Single source of truth, declarative management, audit trail, rollback capability
- **Negative**: Additional operational component, potential single point of failure
- **Mitigation**: Run control plane in dedicated namespace with HA (3 replicas), separate etcd cluster

### Implementation
- gRPC service definitions in `proto/security_control_plane.proto`
- Operators built with Operator SDK (Go)
- Event schemas in `events/security-events.proto`

---

## ADR-003: Dedicated Kong Gateway per Environment

**Status**: Accepted
**Date**: 2026-07-20

### Context
Original design used shared Kong cluster across environments. This created blast radius issues (config error in dev affects prod), noisy neighbor problems, and inability to test gateway upgrades safely.

### Decision
Deploy independent Kong Gateway per environment with:
- **Production**: HA (3+ replicas), dedicated nodes, strict RBAC
- **Staging**: Mirror of prod config, 2 replicas, canary testing
- **Development**: Single replica, ephemeral, per-developer namespaces

### Consequences
- **Positive**: Isolation, independent lifecycles, safe testing, environment-specific tuning
- **Negative**: Operational overhead (3x Kong clusters), config drift risk
- **Mitigation**: GitOps (ArgoCD) for config sync, shared Helm chart with env values, automated drift detection

### Configuration
```yaml
# kong/values-production.yaml
replicaCount: 3
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 500m
    memory: 1Gi
podDisruptionBudget:
  minAvailable: 2
```

---

## ADR-004: Service Mesh with Istio (mTLS STRICT + AuthorizationPolicy)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Needed zero-trust service-to-service communication with fine-grained authorization. Linkerd considered but lacked AuthorizationPolicy granularity and WASM extensibility.

### Decision
Adopt Istio with:
- **PeerAuthentication**: STRICT mTLS mesh-wide
- **AuthorizationPolicy**: Deny-by-default, explicit allow per service
- **RequestAuthentication**: JWT validation for ingress
- **SDS Integration**: SPIRE as certificate provider (replaces Citadel)
- **Sidecar Injection**: Namespace-scoped with opt-out annotation

### Consequences
- **Positive**: Industry standard, rich policy model, SPIRE integration, WASM filters
- **Negative**: Complexity, resource overhead (sidecars), operational learning curve
- **Mitigation**: Ambient mesh evaluation for future, comprehensive runbooks, staged rollout

### Rollout Phases
1. **Phase 1**: Install Istio control plane, enable mTLS PERMISSIVE
2. **Phase 2**: Enable sidecar injection per namespace, validate connectivity
3. **Phase 3**: Switch to STRICT mTLS, deploy AuthorizationPolicies
4. **Phase 4**: Integrate SPIRE SDS, migrate from Citadel

---

## ADR-005: SPIFFE/SPIRE as Identity Foundation

**Status**: Accepted
**Date**: 2026-07-20

### Context
Workload identity was tied to Vault/Kubernetes service accounts. Needed portable, standards-based identity for multi-cluster, multi-cloud, and hybrid workloads.

### Decision
Deploy SPIRE with:
- **Server**: HA (3 replicas) per trust domain, Raft storage
- **Agent**: DaemonSet on every node, workload attestation via K8s PSAT
- **SVIDs**: X.509 (1h TTL) for mTLS, JWT (5m TTL) for API auth
- **Federation**: Bundle endpoint per trust domain, configurable trust policies
- **CSI Driver**: Secret injection for legacy workloads

### Trust Domain Structure
```
qa-vision.io (root)
├── production.qa-vision.io
├── staging.qa-vision.io
├── development.qa-vision.io
├── partner-a.qa-vision.io (federated)
└── partner-b.qa-vision.io (federated)
```

### Consequences
- **Positive**: Standards-based, portable, short-lived certs, federatable, SPIRE SDS for Istio
- **Negative**: New operational component, agent on every node, bootstrap complexity
- **Mitigation**: Automated bootstrap via init containers, health checks, runbooks

---

## ADR-006: Identity Abstraction Layer (Pluggable IdP Adapters)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Organization uses multiple identity providers (Keycloak, Entra ID, Okta). Hardcoding IdP logic in applications creates vendor lock-in and inconsistent user management.

### Decision
Implement Identity Abstraction Layer with:
- **Interface**: `IdentityProvider` with standard CRUD + auth operations
- **Adapters**: KeycloakAdapter, EntraIDAdapter, OktaAdapter, Auth0Adapter, PingAdapter
- **Features**: SCIM 2.0 provisioning, OIDC discovery, JWKS caching, group/role mapping
- **Fallback**: Local user store for break-glass scenarios

### Interface Contract
```go
type IdentityProvider interface {
  CreateUser(ctx, User) (*User, error)
  GetUser(ctx, id) (*User, error)
  UpdateUser(ctx, id, User) (*User, error)
  DeleteUser(ctx, id) error
  ListUsers(ctx, Filter) ([]*User, error)
  Authenticate(ctx, credentials) (*Token, error)
  ValidateToken(ctx, token) (*Claims, error)
  RefreshToken(ctx, refreshToken) (*Token, error)
  ProvisionGroups(ctx, userID, []string) error
  MapRoles(ctx, externalRoles) ([]string, error)
}
```

### Consequences
- **Positive**: Vendor agnostic, consistent API, testable with mock adapter, gradual migration
- **Negative**: Abstraction leakage risk, adapter maintenance burden
- **Mitigation**: Comprehensive adapter test suite, contract testing against real IdPs

---

## ADR-007: Security Domains (Hierarchical Vault Replacement)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Environment-based Vault (dev/staging/prod) didn't support SaaS tenants, multi-cloud, or air-gapped deployments. Needed hierarchical isolation with delegation.

### Decision
Replace environment-based Vault with **Security Domains** CRD:
- **Domain**: Top-level isolation boundary (SaaS tenant, business unit, region)
- **Namespace**: Team/project within domain
- **Application**: Workload-specific secret scope
- **Backend**: Vault cluster per domain (or shared with namespace isolation)

### Domain Types
| Type | Use Case | Vault Topology |
|------|----------|----------------|
| SaaS | Multi-tenant SaaS | Shared cluster, namespace per tenant |
| Multi-Cloud | Workloads across clouds | Vault cluster per cloud region |
| Hybrid | On-prem + cloud | Vault cluster per environment |
| Air-Gapped | Isolated networks | Standalone Vault, manual sync |

### Consequences
- **Positive**: Flexible topology, delegation, compliance boundaries, cost optimization
- **Negative**: Complex Vault operations, cross-domain secret sharing
- **Mitigation**: Domain controller manages Vault namespaces/policies, automated policy generation

---

## ADR-008: Runtime Security with Falco + Tetragon

**Status**: Accepted
**Date**: 2026-07-20

### Context
Needed deep runtime visibility: syscalls, file access, network, k8s audit. Single tool insufficient; Falco excels at syscall rules, Tetragon at eBPF/k8s awareness.

### Decision
Deploy both with complementary roles:
- **Falco**: Syscall rules, k8s audit, custom rule engine, mature rule set
- **Tetragon**: eBPF-based, kernel-level visibility, CIDR tracking, k8s resource correlation
- **Correlation Engine**: Unified pipeline (Fluent Bit → Kafka → Correlator)
- **Response Actions**: Automated (isolate, kill, block) + manual approval

### MITRE ATT&CK Tagging
All rules tagged with ATT&CK techniques:
```yaml
- rule: Terminal shell in container
  mitre:
    - T1059.004  # Unix Shell
    - T1609      # Container Administration Command
  severity: Critical
```

### Consequences
- **Positive**: Defense in depth, comprehensive coverage, automated response
- **Negative**: Alert volume, eBPF kernel dependency, tuning required
- **Mitigation**: Correlation reduces noise, gradual rule enablement, dedicated SOC runbooks

---

## ADR-009: Supply Chain Security (SLSA Level 3 + Sigstore)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Supply chain attacks (SolarWinds, Codecov) require build integrity, provenance, and verification. Needed end-to-end from source to deployment.

### Decision
Implement SLSA Level 3 with:
- **Build**: Tekton pipelines on isolated build clusters
- **Provenance**: SLSA provenance generated per build (build attestation)
- **Signing**: Cosign keyless (OIDC identity) + Sigstore/Rekor transparency log
- **SBOM**: SPDX + CycloneDX generated for every artifact
- **Admission**: Kyverno policy verifying signatures, SLSA level, SBOM presence
- **Verification**: `cosign verify-attestation` in deployment pipeline

### Tekton Pipeline Stages
1. `fetch-source` → 2. `generate-sbom` → 3. `build-image` → 4. `sign-image` → 5. `upload-attestation` → 6. `verify-policy` → 7. `promote`

### Consequences
- **Positive**: Tamper-evident builds, transparency, policy enforcement at deploy
- **Negative**: Build time increase, keyless signing requires OIDC, Rekor dependency
- **Mitigation**: Parallel pipeline stages, cached base images, Rekor mirror

---

## ADR-010: Zero Trust Networking with Cilium

**Status**: Accepted
**Date**: 2026-07-20

### Context
Needed L3/L4/L7 network policies, cluster mesh, encryption, and egress control. Calico lacked L7 visibility and ClusterMesh maturity.

### Decision
Adopt Cilium with:
- **CNI**: eBPF-based, replaces kube-proxy
- **Policies**: CiliumNetworkPolicy (L3/L4/L7), default deny
- **ClusterMesh**: Multi-cluster connectivity with global services
- **Encryption**: WireGuard for pod-to-pod, IPsec for node-to-node
- **Egress Gateway**: Centralized egress with policy
- **DNS Policy**: FQDN-based egress control
- **mTLS Enforcement**: AuthRequired for service mesh integration

### Default Deny Policy
```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: default-deny-all
spec:
  endpointSelector: {}
  ingress:
  - fromEndpoints:
    - matchLabels:
        reserved: system
  egress:
  - toEndpoints:
    - matchLabels:
        k8s:io.kubernetes.pod.namespace: kube-system
```

### Consequences
- **Positive**: High performance, L7 visibility, multi-cluster, encryption
- **Negative**: eBPF kernel requirement (5.10+), complexity, debugging difficulty
- **Mitigation**: Kernel version validation, comprehensive observability (Hubble), runbooks

---

## ADR-011: Security Observability Stack

**Status**: Accepted
**Date**: 2026-07-20

### Context
Security signals scattered across tools. Needed unified observability: metrics, logs, traces, dashboards, alerting.

### Decision
Stack composition:
- **Metrics**: Prometheus + Thanos (long-term storage, global query)
- **Logs**: Loki + Promtail (structured, labeled, correlated)
- **Traces**: Tempo (distributed tracing, exemplars)
- **Dashboards**: Grafana (provisioned via ConfigMaps)
- **Alerting**: Alertmanager + PagerDuty/Slack integration
- **Correlation**: Exemplars linking traces ↔ logs ↔ metrics

### Key Dashboards
1. **Threat Detection**: MITRE heatmap, geo map, severity trends
2. **Security Scorecard**: Category scores, trend, grade
3. **Compliance**: Framework status, control evidence, audit trail
4. **Runtime**: Process tree, network flows, file integrity
5. **Supply Chain**: Build provenance, signature verification, SBOM drift

### Consequences
- **Positive**: Single pane of glass, correlation, cost-effective (Thanos/Tempo)
- **Negative**: Multiple components, storage costs, query complexity
- **Mitigation**: Retention policies, sampling, dashboard standardization

---

## ADR-012: Threat Modeling as Code (STRIDE + PASTA + Attack Trees)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Threat modeling was ad-hoc, documentation drifted from implementation. Needed version-controlled, reviewable, automatable threat models.

### Decision
YAML-based threat model specification with:
- **Methodologies**: STRIDE (per component), PASTA (risk-centric), Attack Trees (scenario)
- **MITRE Mapping**: Every threat maps to ATT&CK techniques
- **Mitigations**: Linked to security controls (policies, config, runtime rules)
- **Residual Risk**: Calculated post-mitigation
- **Test Cases**: Automated validation (Chaos engineering, penetration tests)

### Threat Model Structure
```yaml
apiVersion: security.qa-vision.io/v1
kind: ThreatModel
metadata:
  name: payments-service
spec:
  assets: [...]
  trustBoundaries: [...]
  dataFlows: [...]
  threats:
    - id: TM-001
      stride: Spoofing
      pasta: Stage 3
      attackTree: "AT-001"
      mitre: ["T1078", "T1556"]
      likelihood: HIGH
      impact: CRITICAL
      mitigations: ["mtls", "spiffe", "opa-policy"]
      residualRisk: MEDIUM
      testCases: [...]
```

### Consequences
- **Positive**: Version control, CI integration, automation, audit trail
- **Negative**: Learning curve, maintenance overhead, tooling gaps
- **Mitigation**: Templates per service type, automated STRIDE generation from architecture

---

## ADR-013: Security Scorecards (40+ Metrics, Weighted Scoring)

**Status**: Accepted
**Date**: 2026-07-20

### Context
No quantitative security posture measurement. Needed executive-visible score with drill-down.

### Decision
SecurityScorecardDefinition CRD with:
- **8 Categories**: Identity, Network, Workload, Data, SupplyChain, Operations, Compliance, IncidentResponse
- **40+ Metrics**: Each with PromQL query, target, weight, threshold
- **Weighted Scoring**: Category weights sum to 100%, metric weights within category
- **Grading**: A+ to F scale with trend (impromving/stable/declining)
- **Risk Metrics**: Attack surface, exposure, FAIR quantitative risk

### Category Weights
| Category | Weight | Key Metrics |
|----------|--------|-------------|
| Identity | 20% | MFA coverage, SPIFFE adoption, cert rotation |
| Network | 15% | mTLS coverage, policy coverage, egress control |
| Workload | 15% | Runtime policies, Falco coverage, resource limits |
| Data | 15% | Encryption, secret rotation, DLP |
| SupplyChain | 10% | SLSA level, signature verification, SBOM coverage |
| Operations | 10% | Patch latency, config drift, backup success |
| Compliance | 10% | Framework scores, evidence freshness |
| IncidentResponse | 5% | MTTR, detection coverage, exercise frequency |

### Consequences
- **Positive**: Quantifiable, comparable, trendable, executive-friendly
- **Negative**: Metric definition bias, gaming risk, PromQL complexity
- **Mitigation**: Regular calibration, red-team validation, transparent methodology

---

## ADR-014: Security Platform APIs (OpenAPI 3.1)

**Status**: Accepted
**Date**: 2026-07-20

### Context
Security operations were CLI/tool-specific. Needed unified API for automation, integration, and custom UIs.

### Decision
Complete OpenAPI 3.1 specification covering:
- **Identity**: Workloads, federations, humans, MFA
- **Secrets**: CRUD, versions, rotation policies, audit
- **Certificates**: CRUD, renewal, issuers
- **Policies**: CRUD, evaluation, exemptions
- **Runtime**: Threats, response actions, policies
- **Compliance**: Frameworks, assessments, evidence
- **Audit**: Events (REST + SSE streaming), export
- **Supply Chain**: SBOM, verification, policies
- **Analytics**: Scorecard, risk metrics, trends, threat landscape, compliance, executive summary

### API Standards
- **Authentication**: JWT (Bearer) + API Key
- **Pagination**: Cursor-based with PageInfo
- **Filtering**: Structured query parameters
- **Errors**: RFC 7807 Problem Details
- **Versioning**: URL path (/v1), semantic versioning
- **Rate Limiting**: Token bucket per client

### Consequences
- **Positive**: Automation enablement, integration standard, SDK generation
- **Negative**: API surface maintenance, backward compatibility burden
- **Mitigation**: Deprecation policy (12 months), client SDKs, contract testing

---

## ADR-015: Backward Compatibility Strategy

**Status**: Accepted
**Date**: 2026-07-20

### Context
Existing workloads depend on current Vault, Kong, cert-manager, OPA configurations. Big-bang migration unacceptable.

### Decision
Phased migration with compatibility layers:
1. **Shim Layer**: Translate legacy API calls to new Control Plane
2. **Dual Write**: Write to both old and new systems during transition
3. **Feature Flags**: Per-workload migration toggle
4. **Data Migration**: Automated sync jobs (Vault → Security Domains, etc.)
5. **Validation**: Shadow mode comparison before cutover

### Migration Order
| Phase | Component | Strategy |
|-------|-----------|----------|
| 1 | Identity (SPIRE) | Sidecar injection, dual auth |
| 2 | Secrets | Sync engine, API shim |
| 3 | Certificates | cert-manager → SPIRE issuer |
| 4 | Policies | OPA → Kyverno/OPA hybrid |
| 5 | Network | Cilium alongside existing CNI |
| 6 | Runtime | Falco/Tetragon additive |
| 7 | Supply Chain | New pipeline, old deprecated |
| 8 | Observability | Unified stack, legacy retired |

### Consequences
- **Positive**: Zero-downtime, rollback capability, gradual adoption
- **Negative**: Temporary dual maintenance, sync complexity, extended timeline
- **Mitigation**: Automated validation, clear deprecation timeline, runbooks

---

## ADR-016: Multi-Environment GitOps with ArgoCD

**Status**: Accepted
**Date**: 2026-07-20

### Context
Configuration drift between environments, manual changes, no audit trail for infrastructure changes.

### Decision
ArgoCD App-of-Apps pattern with:
- **Repository**: Monorepo with `environments/{dev,staging,prod}/`
- **Projects**: Per-environment ArgoCD projects with RBAC
- **Sync**: Automated for dev/staging, manual approval for prod
- **Drift Detection**: Automated alerts, auto-remediation for dev
- **Secrets**: SealedSecrets + External Secrets Operator (Vault backend)

### Environment Promotion
```
Dev (auto-sync) → Staging (auto-sync + smoke tests) → Prod (manual + approval)
```

### Consequences
- **Positive**: Declarative, auditable, drift prevention, promotion pipeline
- **Negative**: ArgoCD operational complexity, secret management
- **Mitigation**: ArgoCD HA, disaster recovery tested, break-glass procedures