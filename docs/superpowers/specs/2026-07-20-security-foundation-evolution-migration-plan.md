# Migration Plan
## QA Vision Platform – Security Foundation Evolution

---

## Overview

This migration plan transitions from the current security foundation (Vault, Kong, OPA, cert-manager, basic Falco) to the evolved enterprise security platform over **6 phases spanning 24 weeks**.

### Migration Principles
1. **Zero Downtime**: All migrations maintain service availability
2. **Rollback Ready**: Every phase has tested rollback procedure
3. **Incremental Value**: Each phase delivers standalone security improvement
4. **Parallel Operation**: Legacy and new systems coexist during transition
5. **Automated Validation**: Continuous comparison of legacy vs new behavior

---

## Phase 1: Identity Foundation (Weeks 1-4)

### Objective
Deploy SPIRE as workload identity foundation; establish Identity Abstraction Layer

### Deliverables
- [ ] SPIRE Server (3-node HA) per trust domain
- [ ] SPIRE Agent DaemonSet on all clusters
- [ ] SPIRE CSI Driver for legacy workload injection
- [ ] Identity Abstraction Layer with Keycloak adapter
- [ ] WorkloadIdentity CRD + controller
- [ ] Federation between trust domains (prod ↔ staging)

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 1 | Deploy SPIRE server in dedicated namespace | Health checks, bundle endpoint reachable |
| 2 | Deploy SPIRE agents, configure K8s PSAT attestation | Agent attestation success rate > 99% |
| 3 | Deploy CSI driver, test with sample workload | Secret injection verified |
| 4 | Deploy Identity API, Keycloak adapter | CRUD operations, auth flow tested |

### Rollback
- Disable SPIRE agent DaemonSet → workloads revert to K8s SA tokens
- Keep Vault auth as fallback during transition

### Success Criteria
- 100% of workloads can obtain X.509 SVID
- JWT SVID validation working for API auth
- Federation bundle exchange operational

---

## Phase 2: Security Control Plane (Weeks 5-8)

### Objective
Deploy central orchestration layer; migrate secret management

### Deliverables
- [ ] Security Control Plane gRPC API (3-replica HA)
- [ ] etcd cluster (dedicated, 3-node)
- [ ] NATS JetStream event bus
- [ ] Secrets Operator (Vault backend)
- [ ] Secret CRD + rotation controller
- [ ] API shim for legacy Vault clients

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 5 | Deploy Control Plane core (API, etcd, NATS) | API health, event bus throughput |
| 6 | Implement Secrets Operator with Vault backend | Secret CRUD, rotation trigger test |
| 7 | Deploy Secret CRD, test rotation policies | Rotation executes per schedule |
| 8 | Deploy API shim, dual-write validation | Legacy API calls produce identical results |

### Data Migration
```bash
# Automated sync job: Vault → Security Domain secrets
kubectl create job vault-to-secrets-sync --from=cronjob/vault-sync
# Validates: secret count match, data integrity, metadata preserved
```

### Rollback
- Disable Secrets Operator → Vault remains source of truth
- API shim routes to Vault directly

### Success Criteria
- All secret operations via Control Plane API
- Rotation policies executing automatically
- Audit log parity with Vault audit

---

## Phase 3: Certificates & Service Mesh (Weeks 9-12)

### Objective
Replace cert-manager with SPIRE issuer; deploy Istio with STRICT mTLS

### Deliverables
- [ ] cert-manager SPIRE issuer controller
- [ ] Certificate CRD + controller
- [ ] Istio control plane (dedicated per env)
- [ ] PeerAuthentication STRICT mesh-wide
- [ ] AuthorizationPolicy deny-by-default
- [ ] SDS integration with SPIRE

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 9 | Deploy cert-manager SPIRE issuer | Certificate issued, SPIRE SVID as CA |
| 10 | Migrate Certificate resources to new CRD | cert-manager resources synced |
| 11 | Install Istio control plane (PERMISSIVE) | Sidecar injection, connectivity test |
| 12 | Enable STRICT mTLS, deploy AuthZ policies | mTLS verified, policies enforced |

### Migration Strategy
1. **Canary Namespace**: Migrate `payments` namespace first
2. **Sidecar Injection**: Opt-in via annotation, then namespace default
3. **Policy Rollout**: Audit mode → Warn → Enforce
4. **SDS Cutover**: Switch from Citadel to SPIRE SDS

### Rollback
- `istioctl uninstall` reverts to non-mesh
- cert-manager resumes certificate management
- PeerAuthentication → PERMISSIVE

### Success Criteria
- 100% inter-service traffic mTLS encrypted
- AuthorizationPolicy denying unauthorized calls
- Certificate rotation automated via SPIRE

---

## Phase 4: Network & Runtime Security (Weeks 13-16)

### Objective
Deploy Cilium for zero-trust networking; Falco + Tetragon for runtime protection

### Deliverables
- [ ] Cilium CNI (replace existing CNI)
- [ ] CiliumNetworkPolicy default deny + allow rules
- [ ] ClusterMesh for multi-cluster
- [ ] WireGuard encryption
- [ ] Falco + Tetragon deployment
- [ ] Correlation engine + response automation
- [ ] RuntimePolicy CRD + controller

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 13 | Deploy Cilium alongside existing CNI | Dual CNI test, no connectivity loss |
| 14 | Migrate workloads to Cilium CNI | Pod connectivity, Hubble observability |
| 15 | Deploy default-deny policies per namespace | Policy enforcement verified |
| 16 | Deploy Falco/Tetragon, tune rules | Alert volume manageable, true positives > 80% |

### Cilium Migration (Critical Path)
```bash
# 1. Install Cilium with kube-proxy replacement=false initially
# 2. Validate L3/L4 policies
# 3. Enable kube-proxy replacement (rolling node restart)
# 4. Enable WireGuard encryption
# 5. Deploy ClusterMesh
```

### Rollback
- Cilium: Revert to previous CNI (rolling node restart)
- Falco/Tetragon: DaemonSet scale to 0

### Success Criteria
- All pod traffic controlled by CiliumNetworkPolicy
- Cross-cluster connectivity via ClusterMesh
- Runtime threats detected and auto-responded

---

## Phase 5: Supply Chain & Observability (Weeks 17-20)

### Objective
Implement SLSA Level 3 supply chain; unify security observability stack

### Deliverables
- [ ] Tekton secure build pipeline (SLSA L3)
- [ ] Cosign keyless signing + Rekor
- [ ] SBOM generation (SPDX + CycloneDX)
- [ ] Admission policy (Kyverno) for verification
- [ ] Prometheus/Thanos/Loki/Tempo/Grafana stack
- [ ] Security dashboards (5 core dashboards)
- [ ] Alerting rules + notification routes

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 17 | Deploy Tekton on isolated build cluster | Pipeline executes, provenance generated |
| 18 | Configure Cosign keyless + Rekor | Signature verification, transparency log |
| 19 | Deploy admission verification policy | Unsigned images rejected |
| 20 | Deploy observability stack, import dashboards | Metrics/logs/traces correlated |

### Pipeline Migration
```yaml
# .tekton/secure-build-pipeline.yaml
# Replaces existing CI/CD build stage
# Runs in parallel with legacy for 2 weeks
# Gradual traffic shift: 10% → 50% → 100%
```

### Rollback
- Revert to legacy CI/CD pipeline
- Disable admission verification
- Observability: Legacy Prometheus/Grafana retained

### Success Criteria
- 100% production images signed and verified
- SBOM available for all deployed artifacts
- SLSA Level 3 provenance for all builds
- Unified dashboards showing end-to-end security posture

---

## Phase 6: Threat Modeling, Scorecards & APIs (Weeks 21-24)

### Objective
Implement threat modeling as code; deploy security scorecards; expose platform APIs

### Deliverables
- [ ] ThreatModel CRD + controller
- [ ] SecurityScorecardDefinition CRD + calculator
- [ ] Security Platform API (OpenAPI 3.1)
- [ ] API Gateway with auth/rate limiting
- [ ] Client SDKs (Go, Python, TypeScript)
- [ ] Migration complete: legacy systems decommissioned

### Migration Steps
| Week | Activity | Validation |
|------|----------|------------|
| 21 | Deploy ThreatModel CRD, create initial models | STRIDE/PASTA coverage > 90% |
| 22 | Deploy Scorecard CRD, configure metrics | Scores calculated, trends visible |
| 23 | Deploy Security Platform API | All endpoints functional, SDKs generated |
| 24 | Decommission legacy systems, cutover | Zero legacy dependencies, audit complete |

### Legacy Decommission Checklist
- [ ] Vault clusters decommissioned (data migrated)
- [ ] Shared Kong cluster removed
- [ ] cert-manager uninstalled
- [ ] OPA Gatekeeper policies migrated to Kyverno/OPA
- [ ] Basic Falco rules retired
- [ ] Legacy CI/CD pipeline removed

### Rollback
- All new CRDs support `kubectl delete` with cascade
- API Gateway can route to legacy endpoints (if any remain)
- Scorecard/ThreatModel are additive, no rollback needed

### Success Criteria
- Threat models for all critical services
- Security scorecard updating daily
- APIs serving all security operations
- Zero legacy security infrastructure

---

## Cross-Phase Concerns

### Testing Strategy
| Test Type | When | Tool |
|-----------|------|------|
| Unit | Per component | Go test, pytest |
| Integration | Phase end | Kind clusters, Testcontainers |
| Contract | API changes | Pact, Schemathesis |
| Chaos | Phase 4, 6 | Chaos Mesh, Litmus |
| Penetration | Phase 6 | Internal red team |

### Monitoring During Migration
- **Golden Signals**: Latency, traffic, errors, saturation per component
- **Migration Metrics**: Dual-write parity, sync lag, error rates
- **Security Metrics**: Threat detection rate, policy violations, rotation compliance

### Communication Plan
| Audience | Channel | Frequency |
|----------|---------|-----------|
| Engineering | Slack #security-migration | Daily standup |
| Leadership | Weekly email + dashboard | Weekly |
| Security Team | Dedicated channel | Real-time |
| On-call | PagerDuty + runbooks | As needed |

---

## Risk Mitigation Summary

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SPIRE agent failure | Medium | High | Health checks, auto-restart, fallback to K8s SA |
| Cilium CNI migration | High | Critical | Canary namespace, dual CNI, rollback tested |
| Vault data loss | Low | Critical | Automated backup, verified restore, dual-write |
| Istio STRICT breakage | Medium | High | PERMISSIVE → STRICT gradual, namespace opt-in |
| Supply chain pipeline failure | Medium | Medium | Legacy pipeline parallel, manual promotion fallback |

---

## Timeline Summary

```
Week 1-4:   ████████░░░░░░░░░░░░░░░  Identity Foundation
Week 5-8:   ░░░░████████░░░░░░░░░░░  Control Plane + Secrets
Week 9-12:  ░░░░░░░░████████░░░░░░░  Certificates + Service Mesh
Week 13-16: ░░░░░░░░░░░░████████░░░  Network + Runtime Security
Week 17-20: ░░░░░░░░░░░░░░░░████████  Supply Chain + Observability
Week 21-24: ░░░░░░░░░░░░░░░░░░░░████  Threat Models + Scorecards + APIs
```

**Total: 24 weeks (6 months)**

---

## Go/No-Go Gates

Each phase requires:
1. **Automated Tests Pass**: >95% pass rate
2. **Security Review**: Threat model updated, no critical findings
3. **Performance Baseline**: <10% latency increase
4. **Rollback Tested**: Successful rollback in staging
5. **Stakeholder Sign-off**: Engineering + Security leads approve

---