# Team Onboarding Plan
## QA Vision Platform – Security Foundation Evolution

---

## Program Overview

**Duration**: 5 Weeks (Weeks 0-4 of program, concurrent with Phase 1 start)
**Participants**: 6 Engineers (4 Platform, 2 Security) + 2 Leads
**Goal**: Full team productive on new stack by end of Week 4, certified by Week 6

---

## Week-by-Week Plan

### Week 0: Foundations & Environment Setup (Pre-Program)
**Owner**: Platform Lead | **Format**: Self-paced + 2 sync sessions

| Day | Activity | Duration | Deliverable |
|-----|----------|----------|-------------|
| Mon | Program kickoff, team intros, stack overview | 2 hrs | — |
| Tue | Dev environment: KinD, kubectl, Helm, CLI tools | 4 hrs | Working local cluster |
| Wed | GitOps workflow: ArgoCD, SealedSecrets, Kustomize | 3 hrs | ArgoCD app deployed |
| Thu | Observability stack: PromQL, Grafana, Loki, Tempo | 3 hrs | Dashboard imported |
| Fri | Security tooling: cosign, syft, grype, kyverno CLI | 2 hrs | Signed image pushed |

**Sync Sessions**: Tue 10am, Thu 2pm (1hr each) – unblock, Q&A

---

### Week 1: Identity Foundation (SPIRE + IdP Adapters)
**Owner**: Security Lead | **Format**: 70% hands-on labs, 30% lecture

| Day | Topic | Lab Exercise | Certification Checkpoint |
|-----|-------|--------------|--------------------------|
| Mon | SPIFFE/SPIRE Architecture | Deploy SPIRE server/agent (KinD) | — |
| Tue | Workload Attestation (K8s, Node) | Register workload, verify SVID | SPIRE Basics ✓ |
| Wed | X.509 SVIDs (1h TTL) + Rotation | Issue/rotate cert, verify CSI driver | X.509 SVIDs ✓ |
| Thu | JWT SVIDs (5m TTL) + Federation | Cross-cluster trust domain federation | JWT SVIDs ✓ |
| Fri | IdP Abstraction Layer | Implement KeycloakAdapter + SCIM sync | IdP Adapter ✓ |

**Evening Reading** (1hr/day): SPIRE docs, SPIFFE spec, OIDC spec

**Weekend**: Optional deep-dive – SPIRE Controller Manager

---

### Week 2: Control Plane + Secrets Management
**Owner**: Platform Lead | **Format**: 60% labs, 40% architecture

| Day | Topic | Lab Exercise | Certification Checkpoint |
|-----|-------|--------------|--------------------------|
| Mon | Security Control Plane Architecture | Deploy CP API, etcd, NATS (KinD) | CP Deploy ✓ |
| Tue | Reconcile Engine + Controllers | Write SecretController + Reconcile loop | Controller ✓ |
| Wed | Dual-Write Controller + Shim | Migrate Vault secret → CRD, dual-write | Dual-Write ✓ |
| Thu | Secret Rotation Policies | Implement RotationPolicy, canary rollout | Rotation ✓ |
| Fri | SecurityDomain CRD + Hierarchical Vault | Create Domain → Namespace → App hierarchy | SecDomain ✓ |

**Architecture Reviews**: Wed 2pm, Fri 4pm (30min each)

---

### Week 3: Certificates + Service Mesh (Istio)
**Owner**: Platform Lead + Security Lead (co-teach)

| Day | Topic | Lab Exercise | Certification Checkpoint |
|-----|-------|--------------|--------------------------|
| Mon | SPIRE as Istio CA (SDS Integration) | Configure SPIRE CSI → Istio SDS | SDS ✓ |
| Tue | mTLS Modes: PERMISSIVE → STRICT | Namespace rollout, istioctl analyze | mTLS ✓ |
| Wed | AuthorizationPolicy + RequestAuthentication | Write policies, test with curl/sleep | AuthZ ✓ |
| Thu | Sidecar Injection + Proxy Config | Custom EnvoyFilter, stats config | Injection ✓ |
| Fri | Multi-Cluster Istio (Primary-Remote) | ClusterMesh, cross-cluster mTLS | Multi-Cluster ✓ |

**Pair Programming**: Tue-Thu (Platform + Security pairs)

---

### Week 4: Network + Runtime Security
**Owner**: Security Lead | **Format**: 50% labs, 50% threat modeling

| Day | Topic | Lab Exercise | Certification Checkpoint |
|-----|-------|--------------|--------------------------|
| Mon | Cilium eBPF Architecture | Deploy Cilium (KinD), Hubble UI | Cilium Basics ✓ |
| Tue | L3/L4/L7 NetworkPolicy | Write CiliumNetworkPolicy, test deny | NetPol ✓ |
| Wed | ClusterMesh + WireGuard | Connect 2 KinD clusters, encrypt | ClusterMesh ✓ |
| Thu | Falco + Tetragon (eBPF) | Deploy both, generate syscall events | Runtime Detect ✓ |
| Fri | Correlation Engine + Auto-Response | Write rule → isolate pod → notify | Auto-Response ✓ |

**Red Team Exercise**: Fri 2pm-4pm – Simulated attack, team detects/responds

---

### Week 5: Supply Chain + Observability + APIs
**Owner**: Platform Lead | **Format**: 40% labs, 60% integration

| Day | Topic | Lab Exercise | Certification Checkpoint |
|-----|-------|--------------|--------------------------|
| Mon | SLSA L3 + Tekton Pipeline | Build signed image, verify provenance | SLSA ✓ |
| Tue | Cosign Keyless + Rekor | Sign with OIDC, verify transparency log | Cosign ✓ |
| Wed | SBOM (SPDX/CycloneDX) + Admission | Generate SBOM, Kyverno verify on deploy | SBOM ✓ |
| Thu | Unified Observability | Thanos+Loki+Tempo+Grafana dashboards | Observability ✓ |
| Fri | Security Platform APIs (OpenAPI) | Generate SDK, write integration test | APIs ✓ |

**Integration Test**: Fri 2pm – Full flow: Code → Build → Sign → Deploy → Runtime → Alert

---

### Week 6: Certification & Go-Live Readiness
**Owner**: Both Leads | **Format**: Assessment + Remediation

| Assessment | Format | Passing Score | Retake Policy |
|------------|--------|---------------|---------------|
| **Written Exam** | 2hr, 50 questions (arch, troubleshooting, security) | 80% | 1 retake Week 7 |
| **Practical Lab** | 4hr scenario: Deploy mesh, secure app, respond to alert | Pass/Fail (rubric) | 1 retake Week 7 |
| **Code Review** | Review PR implementing SecurityDomain + Policy | Pass/Fail | Immediate feedback |
| **Incident Simulation** | 1hr: Detect → Contain → Remediate → Postmortem | Pass/Fail | 1 retake Week 7 |

**Certification Awarded**: "QA Vision Security Platform Engineer"
- Valid 2 years
- Renewal: 16hrs continuing education + practical refresh

---

## Training Resources

### Required Reading (Pre-Program)
| Resource | Link | Est. Time |
|----------|------|-----------|
| SPIFFE/SPIRE Documentation | spiffe.io/docs | 4 hrs |
| Istio Security Best Practices | istio.io/latest/docs/security | 3 hrs |
| Cilium eBPF Datapath | docs.cilium.io/en/stable/ | 3 hrs |
| SLSA Framework | slsa.dev/spec/v1.0 | 2 hrs |
| FAIR Risk Model Intro | fairinstitute.org | 2 hrs |

### Hands-On Labs Repository
```bash
git clone https://github.com/qa-vision/security-platform-labs
cd security-platform-labs
make setup  # Provisions KinD clusters, tools
```

### Vendor Training Credits (Budgeted)
| Vendor | Course | Credits | Target |
|--------|--------|---------|--------|
| Isovalent | Cilium Enterprise Essentials | 2 seats | Platform Eng |
| Tetrate | Istio Fundamentals + Security | 2 seats | Platform + Security |
| CNCF | CKS (Certified Kubernetes Security) | 6 seats | All engineers |

---

## Mentorship Program

### Pair Assignments (Weeks 1-4)
| Pair | Senior | Junior | Focus Area |
|------|--------|--------|------------|
| Alpha | Platform Lead | Platform Eng 1 | Control Plane + APIs |
| Beta | Security Lead | Security Eng 1 | SPIRE + Runtime |
| Gamma | Platform Eng 2 | Platform Eng 3 | Mesh + Network |

### Weekly 1:1s (30 min)
- Progress vs. checkpoints
- Blockers & unblocking
- Career development

### Shadow Rotations (Weeks 3-4)
- Each engineer shadows other pair for 1 day
- Cross-pollination of domain knowledge

---

## Knowledge Sharing Rituals

| Ritual | Cadence | Format | Owner |
|--------|---------|--------|-------|
| **Tech Talk Tuesday** | Weekly (Tue 4pm) | 30min deep-dive + demo | Rotating |
| **Incident Review** | Bi-weekly (Thu 10am) | Blameless postmortem | Security Lead |
| **Architecture Decision Log** | Per ADR | Async review + 30min sync | Author |
| **Vendor Office Hours** | Monthly | Q&A with Isovalent/Tetrate | PM |

---

## Assessment Rubric (Practical Lab)

| Dimension | Exceeds (4) | Meets (3) | Approaching (2) | Below (1) |
|-----------|-------------|-----------|-----------------|-----------|
| **Architecture** | Explains tradeoffs, proposes improvements | Correctly implements design | Implements with guidance | Major gaps in understanding |
| **Implementation** | Clean, tested, documented, idiomatic | Working, tested, follows patterns | Working but needs refactor | Doesn't work / major bugs |
| **Troubleshooting** | Root causes fast, uses all tools | Systematic, finds issue | Slow, limited tool use | Cannot diagnose |
| **Security Mindset** | Proactively hardens, threat models | Applies security controls | Basic security awareness | Misses obvious issues |
| **Communication** | Clear docs, teaches others | Clear updates, asks good questions | Updates provided | Poor communication |

**Passing**: Average ≥ 3.0, no dimension < 2

---

## Onboarding Budget (Per Engineer)

| Item | Cost | Notes |
|------|------|-------|
| Vendor Training (Isovalent/Tetrate) | $3,000 | 2 courses |
| CNCF CKS Exam + Prep | $600 | Includes kubernetes.io course |
| Lab Infrastructure (KinD/GCP credits) | $500 | 6 weeks |
| Books/References | $200 | SPIFFE, eBPF, Istio books |
| **Total per Engineer** | **$4,300** | |
| **6 Engineers** | **$25,800** | In program budget |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Certification Rate** | 100% by Week 7 | Exam + Practical |
| **Time to First PR** | < 5 days (Week 1) | GitHub insights |
| **Time to On-Call Ready** | Week 6 | Runbook sign-off |
| **Knowledge Retention** | > 85% at Week 12 | Follow-up quiz |
| **Team Confidence** | > 4.0/5.0 | Weekly pulse survey |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Engineer falls behind checkpoints | Medium | High | Daily sync, buddy system, extended lab hours |
| Vendor training delayed | Low | Medium | Self-paced alternatives, internal SME |
| Lab environment issues | Medium | Low | Pre-provisioned GCP backup clusters |
| Knowledge gaps post-certification | Medium | Medium | Week 8-12 "Learning Fridays" (2hrs) |

---

*Version: 1.0 | Owner: Platform Lead + Security Lead | Review: Weekly during onboarding*