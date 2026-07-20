# Validation Checklist
## QA Vision Platform – Security Foundation Evolution

---

## Overview

This validation checklist ensures each phase of the security foundation evolution meets quality, security, and operational standards before proceeding to the next phase. Each checklist item must be **verified and signed off** by the designated owners.

### Validation Levels
- **L1 - Automated**: CI/CD pipeline gates, unit/integration tests
- **L2 - Manual Verification**: Engineer validation with documented evidence
- **L3 - Security Review**: Security team assessment, threat model validation
- **L4 - Stakeholder Acceptance**: Product/Ops/Security lead sign-off

---

## Phase 1: Identity Foundation (Weeks 1-4)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 1.1 | SPIRE Server HA deployment | `kubectl get pods -n spire -l app=spire-server` | 3/3 Ready, leader elected | Platform | ☐ |
| 1.2 | SPIRE Agent on all nodes | `kubectl get ds -n spire spire-agent` | Desired = Ready on all nodes | Platform | ☐ |
| 1.3 | K8s PSAT attestation working | `spire-agent api fetch x509svid -socketPath /tmp/spire-agent.sock` | SVID issued with k8s selectors | Platform | ☐ |
| 1.4 | CSI Driver secret injection | `kubectl exec test-pod -- cat /secrets/spiffe-svid` | Valid X.509 SVID present | Platform | ☐ |
| 1.5 | Federation bundle exchange | `curl https://staging.spire/qa-vision.io/bundle` | Valid trust bundle returned | Platform | ☐ |
| 1.6 | Identity Abstraction Layer API | `curl -H "Authorization: Bearer $TOKEN" /api/v1/identity/workloads` | 200 OK, valid schema | Platform | ☐ |
| 1.7 | Keycloak adapter CRUD ops | Integration test suite | 100% pass create/read/update/delete | Platform | ☐ |
| 1.8 | Unit test coverage | `go test ./... -cover` | >85% coverage | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 1.9 | X.509 SVID TTL = 1h, rotation 30m before expiry | Inspect cert: `openssl x509 -in svid.pem -text -noout` | NotBefore/NotAfter, rotation logs | Platform | ☐ |
| 1.10 | JWT SVID TTL = 5m, audience correct | Decode JWT: `jq -R 'split(".") | .[1] | @base64d | fromjson'` | exp, aud claims | Platform | ☐ |
| 1.11 | Workload selector uniqueness | `spire-server entry show` | No duplicate (ns, sa) pairs | Platform | ☐ |
| 1.12 | Federation trust domain isolation | Attempt cross-domain SVID use | Rejected with trust error | Security | ☐ |
| 1.13 | Keycloak adapter failover | Stop Keycloak, verify cached tokens work | Graceful degradation documented | Platform | ☐ |
| 1.14 | Break-glass local user access | Disable IdP, use local fallback | Access granted, audit logged | Security | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 1.15 | SPIRE threat model validated | STRIDE analysis doc | No critical/unmitigated threats | Security | ☐ |
| 1.16 | SVID private key protection | HSM/TPM integration verified | Keys non-exportable, audit trail | Security | ☐ |
| 1.17 | Federation policy least privilege | Review allowed SPIFFE IDs | Minimal necessary trust | Security | ☐ |
| 1.18 | Identity API authorization model | RBAC/ABAC policy review | Zero-trust, default deny | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 1.19 | Platform Lead: Identity foundation operational | [ ] |
| 1.20 | Security Lead: Threat model accepted | [ ] |
| 1.21 | On-call: Runbooks complete, alerts tuned | [ ] |

---

## Phase 2: Security Control Plane (Weeks 5-8)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 2.1 | Control Plane API HA | `kubectl get pods -n security-cp` | 3/3 Ready, leader lease | Platform | ☐ |
| 2.2 | etcd cluster health | `etcdctl endpoint health --cluster` | All members healthy | Platform | ☐ |
| 2.3 | NATS JetStream operational | `nats stream ls` | Streams created, consumers active | Platform | ☐ |
| 2.4 | Secrets Operator reconciles | `kubectl get secret -n test-ns test-secret` | Synced from Vault, labels correct | Platform | ☐ |
| 2.5 | Secret rotation executes | CronJob trigger test | Rotation at scheduled time | Platform | ☐ |
| 2.6 | API shim parity test | `diff <(vault kv get) <(cp-api get)` | Zero diff (excluding metadata) | Platform | ☐ |
| 2.7 | Dual-write verification | Chaos test: kill CP, verify Vault write | Both systems consistent | Platform | ☐ |
| 2.8 | Controller leader election | `kubectl get lease -n security-cp` | Single leader, fast failover | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 2.9 | Secret versioning works | Create → Update → List versions | All versions retrievable | Platform | ☐ |
| 2.10 | Rotation policy: grace period respected | Set 1h grace, rotate, verify old valid | Old version accessible during grace | Platform | ☐ |
| 2.11 | Rotation hooks execute | Pre/post rotation webhook test | HTTP 200, payload correct | Platform | ☐ |
| 2.12 | Audit log completeness | Compare CP audit vs Vault audit | 1:1 mapping, no gaps | Security | ☐ |
| 2.13 | etcd backup/restore tested | `etcdctl snapshot save/restore` | Restore < 5 min, data intact | Platform | ☐ |
| 2.14 | Control Plane upgrade (blue/green) | Canary deploy, traffic shift | Zero downtime, rollback < 2 min | Platform | ☐ |
| 2.15 | API rate limiting enforced | Load test: 1000 req/s burst | 429 after limit, quota accurate | Platform | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 2.16 | Control Plane threat model | STRIDE + attack trees | All HIGH mitigated | Security | ☐ |
| 2.17 | etcd encryption at rest | Verify encryption provider | AES-256, key managed by KMS | Security | ☐ |
| 2.18 | NATS auth: mTLS + JWT | Connect without cert/token | Connection rejected | Security | ☐ |
| 2.19 | Secret data encryption in transit | Packet capture verification | TLS 1.3, no plaintext | Security | ☐ |
| 2.20 | Audit log tamper evidence | Append-only, signed entries | Merkle tree or KMS signing | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 2.21 | Platform Lead: Control Plane operational | [ ] |
| 2.22 | Security Lead: Crypto controls validated | [ ] |
| 2.23 | Compliance: Audit trail meets SOC2 | [ ] |

---

## Phase 3: Certificates & Service Mesh (Weeks 9-12)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 3.1 | cert-manager SPIRE issuer | `kubectl get clusterissuer spire-issuer` | Ready=True, CA cert from SPIRE | Platform | ☐ |
| 3.2 | Certificate CRD auto-renewal | Create cert with 24h duration | Renewed at 75% lifetime | Platform | ☐ |
| 3.3 | Istio control plane (per env) | `istioctl proxy-status` | All proxies SYNCED | Platform | ☐ |
| 3.4 | PeerAuthentication STRICT | `kubectl get peerauthentication -A` | Mode=STRICT in all ns | Platform | ☐ |
| 3.5 | AuthorizationPolicy deny-by-default | Deploy test service, call without policy | 403/503 response | Platform | ☐ |
| 3.6 | SDS integration with SPIRE | `istioctl pc secret pod/<pod> -o json` | SVID from SPIRE, not Citadel | Platform | ☐ |
| 3.7 | mTLS verification | `istioctl x authz check <pod>` | All peers mTLS | Platform | ☐ |
| 3.8 | Sidecar injection opt-in/opt-out | Annotation test | Injection follows annotation | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 3.9 | Certificate private key rotation | Force renew, verify new key | Old key revoked, new key distinct | Platform | ☐ |
| 3.10 | Cert validity: 90d, renew 15d before | Inspect issued cert | NotAfter - NotBefore = 90d | Platform | ☐ |
| 3.11 | AuthZ policy: namespace isolation | Cross-ns call without policy | Denied, audit log entry | Security | ☐ |
| 3.12 | AuthZ policy: service-to-service allow | Valid policy, call succeeds | 200 OK, mTLS verified | Platform | ☐ |
| 3.13 | RequestAuthentication JWT validation | Invalid/expired token test | 401, no upstream call | Security | ☐ |
| 3.14 | Envoy config dump inspection | `istioctl proxy-config all <pod>` | SDS config present, certs valid | Platform | ☐ |
| 3.15 | Canary namespace migration | Migrate `payments` ns first | Zero errors, metrics baseline | Platform | ☐ |
| 3.16 | PERMISSIVE → STRICT transition | Monitor during transition | No 5xx spikes, mTLS % → 100% | Platform | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 3.17 | Service mesh threat model | STRIDE per component | No critical gaps | Security | ☐ |
| 3.18 | AuthorizationPolicy bypass test | Fuzz policy engine | No decision bypass | Security | ☐ |
| 3.19 | Certificate transparency | CT log submission verified | All certs logged | Security | ☐ |
| 3.20 | Private key compromise procedure | Drill: revoke + rotate < 15 min | Procedure documented, tested | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 3.21 | Platform Lead: Mesh operational | [ ] |
| 3.22 | Security Lead: mTLS + AuthZ validated | [ ] |
| 3.23 | App Teams: Migration path clear | [ ] |

---

## Phase 4: Network & Runtime Security (Weeks 13-16)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 4.1 | Cilium CNI operational | `cilium status --wait` | All components healthy | Platform | ☐ |
| 4.2 | Hubble observability enabled | `hubble observe --follow` | Flows visible, no drops | Platform | ☐ |
| 4.3 | Default deny CiliumNetworkPolicy | Deploy test pod, no policy | Ingress/Egress dropped | Platform | ☐ |
| 4.4 | L7 HTTP policy enforcement | Policy allow GET /health only | POST returns 403 | Platform | ☐ |
| 4.5 | ClusterMesh connectivity | `cilium clustermesh status` | All clusters connected | Platform | ☐ |
| 4.6 | WireGuard encryption enabled | `cilium status --verbose` | Encryption: WireGuard | Platform | ☐ |
| 4.7 | Falco rules loaded | `falco --list` | >100 rules, custom loaded | Platform | ☐ |
| 4.8 | Tetragon eBPF programs attached | `tetragon getevents` | Events flowing, no errors | Platform | ☐ |
| 4.9 | Correlation engine pipeline | Inject test event → alert | End-to-end < 30 sec | Platform | ☐ |
| 4.10 | RuntimePolicy CRD enforced | Create policy, trigger violation | Action executed (alert/block) | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 4.11 | Cilium migration: zero downtime | Rolling node migration | Pod connectivity maintained | Platform | ☐ |
| 4.12 | DNS policy: FQDN egress control | Policy allow api.stripe.com only | Other domains blocked | Security | ☐ |
| 4.13 | Egress gateway: centralized egress | Traffic via gateway nodes | Source IP = gateway | Platform | ☐ |
| 4.14 | Falco rule tuning: false positive < 5% | 7-day baseline review | Alert volume, FP rate | Security | ☐ |
| 4.15 | Tetragon: process execution detection | Exec shell in container | Event captured, enriched | Security | ☐ |
| 4.16 | MITRE ATT&CK tagging coverage | Rule audit spreadsheet | >90% techniques covered | Security | ☐ |
| 4.17 | Automated response: isolate pod | Trigger critical threat | Pod network isolated < 10s | Security | ☐ |
| 4.18 | Automated response: kill process | Trigger exec threat | Process killed, alert fired | Security | ☐ |
| 4.19 | Network flow correlation | Multi-hop attack simulation | Full path reconstructed | Security | ☐ |
| 4.20 | Alert routing: PagerDuty/Slack | Fire test alerts per severity | Correct route, dedup works | Platform | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 4.21 | Cilium threat model | eBPF attack surface review | No kernel exploit path | Security | ☐ |
| 4.22 | Falco/Tetragon evasion test | Known bypass techniques | Detected or mitigated | Security | ☐ |
| 4.23 | Response action safety | Rollback procedure for each | Tested in staging | Security | ☐ |
| 4.24 | Data privacy: no secrets in alerts | Alert payload inspection | No PII, keys, tokens | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 4.25 | Platform Lead: Cilium + Runtime operational | [ ] |
| 4.26 | Security Lead: Detection/Response validated | [ ] |
| 4.27 | SOC Lead: Runbooks complete, team trained | [ ] |

---

## Phase 5: Supply Chain & Observability (Weeks 17-20)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 5.1 | Tekton pipeline executes | `tkn pipelinerun logs -f` | All tasks succeed, provenance | Platform | ☐ |
| 5.2 | SLSA Level 3 provenance generated | `cosign verify-attestation` | PASS, predicate valid | Platform | ☐ |
| 5.3 | Cosign keyless signing works | `cosign sign --yes $IMAGE` | Signature verified, Rekor entry | Platform | ☐ |
| 5.4 | SBOM generated (SPDX + CycloneDX) | `syft $IMAGE -o spdx-json` | Valid schema, complete deps | Platform | ☐ |
| 5.5 | Admission policy rejects unsigned | Deploy unsigned image | Rejected by Kyverno | Platform | ☐ |
| 5.6 | Admission policy enforces SLSA | Deploy SLSA L1 image | Rejected, audit log | Platform | ☐ |
| 5.7 | Prometheus/Thanos metrics | `curl /metrics` | Security metrics exposed | Platform | ☐ |
| 5.8 | Loki log aggregation | `logcli query '{app="falco"}'` | Structured logs, labels | Platform | ☐ |
| 5.9 | Tempo traces with exemplars | Trace ID in logs → Tempo | Exemplar linkage works | Platform | ☐ |
| 5.10 | Grafana dashboards provisioned | `kubectl get cm -n monitoring` | 5 dashboards, auto-provisioned | Platform | ☐ |
| 5.11 | Alertmanager routing | Alert test per receiver | Correct route, no drops | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 5.12 | Build reproducibility | Build twice, compare digests | Identical digests | Platform | ☐ |
| 5.13 | SBOM drift detection | Deploy → modify dep → redeploy | Drift alert fired | Security | ☐ |
| 5.14 | Vulnerability scanning in pipeline | Trivy/Grype in pipeline | Critical/High block deploy | Security | ☐ |
| 5.15 | Rekor transparency verification | `rekor search --sha $DIGEST` | Entry found, inclusion proof | Security | ☐ |
| 5.16 | Dashboard: Threat Detection | Load dashboard, verify data | MITRE heatmap, geo map | Security | ☐ |
| 5.17 | Dashboard: Security Scorecard | Load dashboard, verify scores | Categories, trends, grade | Security | ☐ |
| 5.18 | Dashboard: Compliance | Load dashboard, verify frameworks | Control status, evidence links | Compliance | ☐ |
| 5.19 | Dashboard: Runtime | Load dashboard, verify flows | Process tree, network map | Platform | ☐ |
| 5.20 | Dashboard: Supply Chain | Load dashboard, verify builds | Provenance, signatures, SBOM | Platform | ☐ |
| 5.21 | Alert: critical threat → PagerDuty | Trigger critical Falco rule | Page fired, runbook linked | Platform | ☐ |
| 5.22 | Alert: scorecard degradation | Simulate score drop >10% | Alert fired, dashboard updated | Platform | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 5.23 | Supply chain threat model | SLSA threat matrix | All L3 requirements met | Security | ☐ |
| 5.24 | Keyless signing: OIDC token audit | Token scope, audience | Least privilege, short TTL | Security | ☐ |
| 5.25 | Observability data retention | Thanos/Loki/Tempo config | Compliance-aligned retention | Security | ☐ |
| 5.26 | Dashboard data accuracy | Cross-ref with source systems | <1% discrepancy | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 5.27 | Platform Lead: Supply chain + Obs operational | [ ] |
| 5.28 | Security Lead: SLSA L3 verified | [ ] |
| 5.29 | Compliance Lead: Dashboards meet audit needs | [ ] |

---

## Phase 6: Threat Modeling, Scorecards & APIs (Weeks 21-24)

### L1 Automated Gates
| # | Check | Tool/Command | Pass Criteria | Owner | Status |
|---|-------|--------------|---------------|-------|--------|
| 6.1 | ThreatModel CRD reconciles | `kubectl get threatmodel` | Status=Ready, mitigations linked | Platform | ☐ |
| 6.2 | STRIDE auto-generation from arch | Tool output review | >80% coverage vs manual | Security | ☐ |
| 6.3 | SecurityScorecardDefinition CRD | `kubectl get scorecard` | Calculates daily, history stored | Platform | ☐ |
| 6.4 | Scorecard metric PromQL valid | `promtool check rules` | All queries parse, execute | Platform | ☐ |
| 6.5 | OpenAPI 3.1 spec valid | `spectral lint openapi.yaml` | No errors, warnings < 5 | Platform | ☐ |
| 6.6 | API Gateway deployed | `kubectl get gateway` | Ready, TLS terminated | Platform | ☐ |
| 6.7 | SDKs generated (Go, Python, TS) | `go build ./sdk/go/...` | Compile, tests pass | Platform | ☐ |
| 6.8 | API contract tests | `schemathesis run openapi.yaml` | All endpoints 2xx/4xx as spec | Platform | ☐ |
| 6.9 | Legacy decommission verification | `kubectl get vault,kong,cert-manager` | Not found | Platform | ☐ |

### L2 Manual Verification
| # | Check | Method | Evidence Required | Owner | Status |
|---|-------|--------|-------------------|-------|--------|
| 6.10 | Threat model: payments service | Review TM-001 to TM-020 | STRIDE+PASTA+AttackTrees | Security | ☐ |
| 6.11 | Threat model: residual risk ≤ MEDIUM | Risk register review | No HIGH/CRITICAL residual | Security | ☐ |
| 6.12 | Scorecard: 8 categories, 40+ metrics | Metric inventory spreadsheet | All metrics have PromQL | Security | ☐ |
| 6.13 | Scorecard: weights sum to 100% | Category weight config | Verified | Security | ☐ |
| 6.14 | Scorecard: grade calculation | Known input → expected grade | A+/A/A-/B+/B/B-/C+/C/C-/D/F | Security | ☐ |
| 6.15 | Risk metrics: FAIR calculation | Sample scenario → ALE | Matches manual calc | Security | ☐ |
| 6.16 | API: identity endpoints | Postman collection test | CRUD, federations, MFA flow | Platform | ☐ |
| 6.17 | API: secrets endpoints | Postman collection test | CRUD, versions, rotation, audit | Platform | ☐ |
| 6.18 | API: certificates endpoints | Postman collection test | CRUD, renewal, issuers | Platform | ☐ |
| 6.19 | API: policies endpoints | Postman collection test | CRUD, evaluate, exemptions | Platform | ☐ |
| 6.20 | API: runtime endpoints | Postman collection test | Threats, response, policies | Platform | ☐ |
| 6.21 | API: compliance endpoints | Postman collection test | Frameworks, assessments, evidence | Platform | ☐ |
| 6.22 | API: audit SSE streaming | `curl -N /audit/events` | Events stream, filters work | Platform | ☐ |
| 6.23 | API: supply chain endpoints | Postman collection test | SBOM, verify, policies | Platform | ☐ |
| 6.24 | API: analytics endpoints | Postman collection test | Scorecard, risk, trends, exec | Platform | ☐ |
| 6.25 | API authentication: JWT + API Key | Auth test matrix | 401 without, 200 with valid | Security | ☐ |
| 6.26 | API rate limiting: tiered quotas | Load test per tier | Quotas enforced, headers | Platform | ☐ |

### L3 Security Review
| # | Check | Method | Pass Criteria | Owner | Status |
|---|-------|--------|---------------|-------|--------|
| 6.27 | API threat model | OWASP API Top 10 | All mitigated | Security | ☐ |
| 6.28 | Threat model review process | PR template, required reviewers | Enforced in CI | Security | ☐ |
| 6.29 | Scorecard gaming resistance | Red team: manipulate metrics | Score reflects reality | Security | ☐ |
| 6.30 | API pagination/cursor security | Cursor tampering test | No data leakage | Security | ☐ |

### L4 Stakeholder Acceptance
| # | Check | Sign-off Required |
|---|-------|-------------------|
| 6.31 | Platform Lead: All APIs operational | [ ] |
| 6.32 | Security Lead: Threat models + Scorecards validated | [ ] |
| 6.33 | Architecture Review Board: Final architecture | [ ] |
| 6.34 | CISO: Production readiness | [ ] |
| 6.35 | Compliance: Audit evidence complete | [ ] |

---

## Cross-Cutting Validations (All Phases)

### Performance Baselines
| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| API p99 latency | <200ms | <100ms | Load test 1000 RPS |
| Secret read latency | <50ms | <20ms | Control Plane API |
| Certificate issuance | <5s | <2s | SPIRE + cert-manager |
| Policy evaluation | <10ms | <5ms | OPA/Kyverno |
| Threat detection → alert | <30s | <10s | Falco/Tetragon pipeline |
| Build + sign + attest | <10min | <5min | Tekton pipeline |

### Reliability Gates
| Check | Target | Measurement |
|-------|--------|-------------|
| Control Plane uptime | 99.95% | SLO dashboard |
| SPIRE uptime | 99.99% | SLO dashboard |
| Cilium agent uptime | 99.99% | SLO dashboard |
| Observability pipeline lag | <60s | Prometheus/Thanos/Grafana |
| Backup restore RTO | <15 min | Quarterly drill |
| Backup restore RPO | <1 hour | Continuous backup |

### Security Gates
| Check | Requirement |
|-------|-------------|
| No critical CVEs in container images | Trivy scan in CI |
| All secrets rotated per policy | Audit report |
| No hardcoded credentials | GitLeaks/Semgrep in CI |
| All endpoints TLS 1.3 | sslyze scan |
| RBAC least privilege | kube-audit / krane |
| Network policies cover all namespaces | Default deny verified |

---

## Sign-off Matrix

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------|---------|---------|---------|---------|---------|---------|
| Platform Lead | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Security Lead | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Compliance Lead | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| SRE/On-call Lead | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Architecture Review | | | [ ] | | [ ] | [ ] |
| CISO | | | | | | [ ] |

---

## Go/No-Go Decision Template

**Phase**: ____
**Date**: ____
**Decision**: ☐ GO ☐ NO-GO ☐ CONDITIONAL GO

**Blockers** (if NO-GO):
1. ____
2. ____

**Conditions** (if CONDITIONAL):
1. ____ (Due: ____)
2. ____ (Due: ____)

**Signatures**:
- Platform Lead: _________________ Date: ____
- Security Lead: _________________ Date: ____
- Compliance Lead: _________________ Date: ____

---

## Continuous Validation (Post-Migration)

### Weekly Automated Checks
- [ ] Security scorecard calculation runs
- [ ] Threat model drift detection (compare with architecture)
- [ ] Certificate expiry scan (next 30 days)
- [ ] Secret rotation compliance
- [ ] Policy violation trend
- [ ] Observability pipeline health

### Monthly Reviews
- [ ] Scorecard trend review with stakeholders
- [ ] Threat model update (new features, incidents)
- [ ] Incident response drill (tabletop)
- [ ] Supply chain SBOM freshness audit
- [ ] Access review: break-glass, admin roles

### Quarterly Deep Dives
- [ ] Full penetration test (rotate focus areas)
- [ ] Disaster recovery drill (full restore)
- [ ] Architecture review (new threats, tech)
- [ ] Vendor/security tool evaluation
- [ ] Compliance framework update

---