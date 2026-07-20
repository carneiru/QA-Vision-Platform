# Vendor Evaluation Matrix
## QA Vision Platform – Security Foundation Evolution

---

## Evaluation Criteria & Weighting

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Technical Fit** | 25% | Feature coverage, architecture alignment, performance |
| **Operational Maturity** | 20% | Stability, upgrade process, observability, debugging |
| **Security Posture** | 15% | Supply chain, certifications, vulnerability response |
| **Vendor Viability** | 15% | Funding, roadmap, customer base, lock-in risk |
| **Total Cost of Ownership** | 15% | License, infrastructure, ops, training, 3-year TCO |
| **Ecosystem & Integration** | 10% | CNCF graduation, K8s native, API compatibility |

---

## 1. Service Mesh: Istio vs Linkerd vs Cilium (Mesh) vs Consul

| Criterion | **Istio (Tetrate Distro)** | Linkerd | Cilium (Mesh) | Consul Connect |
|-----------|---|---|---|---|
| **Technical Fit (25%)** | 9/10 | 7/10 | 7/10 | 6/10 |
| - mTLS STRICT + AuthZ | ✅ Native | ✅ Native | ✅ Beta | ✅ Native |
| - SPIFFE/SPIRE SDS | ✅ Full | ⚠️ Limited | ✅ Full | ⚠️ Vault only |
| - Multi-cluster (ClusterMesh) | ✅ Multi-primary | ✅ Multi-cluster | ✅ Native | ✅ Federation |
| - L7 AuthZ (AuthZ Policy) | ✅ Rich | ❌ Basic | ⚠️ Emerging | ✅ Intentions |
| - Ambient/ Sidecarless | ✅ Alpha (Istio 1.20) | ❌ | ✅ Cilium Mesh | ❌ |
| **Operational Maturity (20%)** | 7/10 | 9/10 | 7/10 | 6/10 |
| - Upgrade complexity | Medium | Low | Medium | High |
| - Debugging tools | istioctl, dashboards | viz, tap | Cilium CLI, Hubble | consul connect |
| - Resource overhead | High (sidecar) | Low (sidecar) | Medium (ebpf) | Medium |
| **Security Posture (15%)** | 9/10 | 8/10 | 8/10 | 7/10 |
| - FIPS builds | ✅ Tetrate | ❌ | ⚠️ Enterprise | ✅ Enterprise |
| - CVE response | <72h (Tetrate) | <1wk | <72h (Isovalent) | <1wk |
| - Supply chain (SLSA) | L3 (Tetrate) | L2 | L2 | L1 |
| **Vendor Viability (15%)** | 8/10 | 9/10 | 9/10 | 7/10 |
| - Company | Tetrate (Series B) | Buoyant (Series B) | Isovalent (Series C) | HashiCorp (Public) |
| - CNCF Status | Graduated | Graduated | Graduated | Graduated |
| - Roadmap alignment | High (Ambient, WASM) | High (Mesh) | High (eBPF) | Medium (VM focus) |
| **TCO 3-Year (15%)** | $1.2M | $0.6M | $0.9M | $1.5M |
| - License | $480K (Tetrate) | $0 | $360K (Enterprise) | $720K (Enterprise) |
| - Infra (sidecars) | $480K | $240K | $180K (eBPF) | $360K |
| - Ops (2 FTE) | $240K | $360K | $360K | $420K |
| **Ecosystem (10%)** | 9/10 | 8/10 | 9/10 | 7/10 |
| **WEIGHTED SCORE** | **8.2** | **7.6** | **7.7** | **6.4** |

### **Recommendation: Istio (Tetrate Distro)**
**Rationale**: Best SPIFFE/SPIRE integration, richest AuthZ, multi-cluster maturity, FIPS support for compliance. Tetrate provides enterprise support without full vendor lock-in (upstream compatible). Ambient mode roadmap aligns with future sidecarless vision.

---

## 2. CNI / Network Policy: Cilium vs Calico vs Antrea vs AWS VPC CNI

| Criterion | **Cilium (Isovalent Enterprise)** | Calico Enterprise | Antrea | AWS VPC CNI |
|-----------|---|---|---|---|
| **Technical Fit (25%)** | 10/10 | 7/10 | 6/10 | 4/10 |
| - eBPF L3/L4/L7 | ✅ Native | ⚠️ Partial (VPP) | ❌ | ❌ |
| - ClusterMesh (multi-cluster) | ✅ Native | ✅ Federation | ⚠️ Limited | ❌ |
| - WireGuard encryption | ✅ Native | ✅ WireGuard | ❌ | ❌ |
| - Egress Gateway | ✅ Native | ✅ Egress | ⚠️ Basic | ❌ |
| - DNS Policy / L7 visibility | ✅ Full | ⚠️ Limited | ❌ | ❌ |
| - Hubble observability | ✅ Native | ❌ | ❌ | ❌ |
| **Operational Maturity (20%)** | 8/10 | 9/10 | 7/10 | 9/10 |
| - Kernel requirements | 5.10+ (BTF/CO-RE) | Any | Any | Any |
| - Upgrade process | In-place, rolling | In-place | In-place | Managed |
| - Troubleshooting | Hubble, cilium-dbg | calicoctl | antctl | VPC flow logs |
| **Security Posture (15%)** | 9/10 | 7/10 | 6/10 | 5/10 |
| - Least privilege eBPF | ✅ Verified | N/A | N/A | N/A |
| - CVE response | <48h (Isovalent) | <1wk | <1wk | AWS SLAs |
| **Vendor Viability (15%)** | 9/10 | 8/10 | 7/10 | N/A (Cloud) |
| **TCO 3-Year (15%)** | $1.1M | $0.9M | $0.6M* | $0.4M** |
| - License (prod only) | $600K | $540K | $0 | $0 |
| - Infra (nodes) | $360K | $360K | $360K | Included |
| - Ops | $140K | $0K | $240K | $40K |
| **Ecosystem (10%)** | 9/10 | 8/10 | 7/10 | 10/10 (AWS) |
| **WEIGHTED SCORE** | **9.0** | **7.5** | **6.3** | **4.8** |

*\* Self-supported, higher ops cost **\* Included in EC2 but limited features*

### **Recommendation: Cilium (Isovalent Enterprise for Production)**
**Rationale**: Only solution providing eBPF L7 policy, ClusterMesh, WireGuard, Hubble, and Egress Gateway natively. Isovalent Enterprise for production gives kernel compatibility guarantees, CVE SLA, and TAC support. OSS for dev/staging.

---

## 3. Workload Identity: SPIRE vs Vault Agent vs cert-manager vs IRSA

| Criterion | **SPIRE (SPIFFE)** | Vault Agent Injector | cert-manager + Vault | IRSA (AWS) / WIF (GCP) |
|-----------|---|---|---|---|
| **Technical Fit (25%)** | 10/10 | 6/10 | 7/10 | 5/10 |
| - SPIFFE standard | ✅ Reference impl | ❌ Proprietary | ❌ X.509 only | ❌ Cloud-specific |
| - X.509 SVID (1h TTL) | ✅ Native | ✅ Via Vault PKI | ✅ Native | ❌ |
| - JWT SVID (5m TTL) | ✅ Native | ❌ | ❌ | ✅ OIDC token |
| - Cross-cluster federation | ✅ Native | ⚠️ Manual | ❌ | ❌ |
| - CSI Driver for K8s | ✅ Native | ✅ Vault CSI | ✅ CSI | ❌ |
| - SDS for Istio | ✅ Native | ❌ | ❌ | ❌ |
| - Workload attestation | K8s PSAT, AWS/GCP/Azure | K8s SA | K8s SA | Cloud IAM |
| **Operational Maturity (20%)** | 8/10 | 9/10 | 9/10 | 10/10 |
| - HA/DR | 3+ servers, Raft | Vault HA | cert-manager HA | Cloud managed |
| - Rotation automation | ✅ Native | ✅ Native | ✅ Native | ✅ Cloud |
| **Security Posture (15%)** | 10/10 | 7/10 | 8/10 | 7/10 |
| - Short-lived creds | 1h/5min | Configurable | Configurable | 1hr (AWS) |
| - HSM support | ✅ CloudHSM, Azure KV | ✅ HSM | ✅ HSM | Cloud KMS |
| - Audit logging | Full SPIRE API | Vault audit | cert-manager log | CloudTrail |
| **Vendor Viability (15%)** | 9/10 (CNCF Graduated) | 9/10 (HashiCorp) | 9/10 (CNCF Graduated) | N/A |
| **TCO 3-Year (15%)** | $0.9M | $1.2M | $0.7M | $0.3M* |
| - Infra (3 clusters) | $540K | $360K | $240K | $0 |
| - Ops (1.5 FTE) | $360K | $480K | $240K | $50K |
| - Vendor support | $0 (optional) | $360K | $220K | $250K |
| **Ecosystem (10%)** | 9/10 | 8/10 | 8/10 | 6/10 |
| **WEIGHTED SCORE** | **9.3** | **7.4** | **7.6** | **5.8** |

*\* Cloud IAM included but lacks portability*

### **Recommendation: SPIRE**
**Rationale**: Only solution providing portable, standards-based (SPIFFE) identity with federation, SDS for Istio, JWT+X.509 SVIDs, and multi-cloud/hybrid support. Foundation for zero-trust architecture.

---

## 4. Runtime Security: Falco + Tetragon vs Sysdig vs Aqua vs Datadog

| Criterion | **Falco + Tetragon (OSS)** | Sysdig Secure | Aqua Security | Datadog Security |
|-----------|---|---|---|---|
| **Technical Fit (25%)** | 9/10 | 8/10 | 8/10 | 6/10 |
| - Syscall monitoring | ✅ Falco | ✅ | ✅ | ✅ |
| - eBPF (Tetragon) | ✅ Native | ✅ | ✅ | ⚠️ Limited |
| - K8s audit logging | ✅ Falco | ✅ | ✅ | ✅ |
| - MITRE ATT&CK tagging | ✅ Community rules | ✅ Built-in | ✅ Built-in | ⚠️ Basic |
| - Auto-response (isolate/kill) | ✅ Tetragon | ✅ | ✅ | ❌ |
| - Policy-as-code (CRD) | ✅ RuntimePolicy | ✅ | ✅ | ❌ |
| - GitOps integration | ✅ Native | ⚠️ API | ⚠️ API | ✅ |
| **Operational Maturity (20%)** | 7/10 | 9/10 | 9/10 | 8/10 |
| - Rule tuning | Manual (8-wk program) | Assisted | Assisted | Limited |
| - False positive reduction | Correlation engine (73%) | ML-based | ML-based | Basic |
| **Security Posture (15%)** | 8/10 | 9/10 | 9/10 | 7/10 |
| - Supply chain (signed rules) | ✅ Cosign | ✅ | ✅ | ✅ |
| - Kernel exploit mitigation | eBPF (safer) | Kernel module | Kernel module | Kernel module |
| **Vendor Viability (15%)** | 9/10 (CNCF) | 8/10 (Private) | 8/10 (Private) | 10/10 (Public) |
| **TCO 3-Year (15%)** | $0.6M | $2.1M | $1.8M | $1.5M* |
| - License | $0 | $1.2M | $1.1M | $0.9M |
| - Infra/ops | $600K | $900K | $700K | $600K |
| **Ecosystem (10%)** | 9/10 | 8/10 | 8/10 | 9/10 |
| **WEIGHTED SCORE** | **8.1** | **8.5** | **8.4** | **7.0** |

*\* Included in platform spend*

### **Recommendation: Falco + Tetragon (Self-managed)**
**Rationale**: Best technical fit with eBPF + syscall dual engine, MITRE tagging, CRD-based policies, auto-response, and zero license cost. 8-week tuning program addresses operational maturity gap. Correlation engine achieves 73% FP reduction. Vendor alternatives cost 3-4x for similar capability.

---

## 5. Supply Chain: Tekton + Cosign + Rekor vs GitHub Actions + Cosign vs GitLab + Cosign

| Criterion | **Tekton + Cosign + Rekor (SLSA L3)** | GitHub Actions + Cosign | GitLab CI + Cosign |
|-----------|---|---|---|
| **Technical Fit (25%)** | 10/10 | 7/10 | 7/10 |
| - SLSA Level 3 | ✅ Hermetic, reproducible | ⚠️ L2 max (shared runners) | ⚠️ L2 max |
| - Keyless signing (OIDC) | ✅ Cosign keyless | ✅ Cosign keyless | ✅ Cosign keyless |
| - Transparency log (Rekor) | ✅ Native | ✅ Native | ✅ Native |
| - SBOM (SPDX + CycloneDX) | ✅ Syft in pipeline | ✅ Syft | ✅ Syft |
| - Policy admission (Kyverno) | ✅ Native CRD | ⚠️ External | ⚠️ External |
| - Isolated build clusters | ✅ Dedicated | ❌ Shared | ❌ Shared |
| - Hermetic builds | ✅ Configurable | ❌ | ❌ |
| **Operational Maturity (20%)** | 7/10 | 9/10 | 8/10 |
| - Learning curve | High | Low | Medium |
| - Debugging | Tekton Dashboard | Native UI | Native UI |
| **Security Posture (15%)** | 10/10 | 7/10 | 7/10 |
| - Build isolation | gVisor/Kata | None | None |
| - Provenance verification | SLSA L3 | L2 | L2 |
| **Vendor Viability (15%)** | 9/10 (CNCF) | 10/10 (Microsoft) | 8/10 (Private) |
| **TCO 3-Year (15%)** | $1.8M | $0.6M | $0.8M |
| - Build infra (isolated) | $1.8M | $0.6M (shared) | $0.8M |
| - License | $0 | $0 | $0 (included) |
| **Ecosystem (10%)** | 8/10 | 10/10 | 9/10 |
| **WEIGHTED SCORE** | **8.9** | **7.7** | **7.6** |

### **Recommendation: Tekton + Cosign + Rekor (Isolated Build Clusters)**
**Rationale**: Only path to SLSA Level 3 with hermetic, reproducible builds and dedicated isolation. Higher upfront cost justified by supply chain risk reduction (SR-03: High 15). GitHub Actions for non-critical paths.

---

## 6. Secrets Management: External Secrets Operator + Vault vs SealedSecrets vs AWS Secrets Manager

| Criterion | **ESO + Vault (Per Domain)** | SealedSecrets + Vault | AWS Secrets Manager |
|-----------|---|---|---|
| **Technical Fit (25%)** | 10/10 | 7/10 | 5/10 |
| - Security Domains (hierarchical) | ✅ Native | ❌ Flat | ❌ Flat |
| - Dynamic secrets | ✅ Vault | ❌ Static only | ✅ RDS only |
| - Rotation policies | ✅ CRD-driven | ❌ Manual | ✅ Native |
| - Multi-cloud / hybrid | ✅ Native | ✅ K8s-native | ❌ AWS only |
| - GitOps (ArgoCD) | ✅ ESO + SealedSecrets | ✅ Native | ⚠️ External |
| **Operational Maturity (20%)** | 8/10 | 9/10 | 10/10 |
| **Security Posture (15%)** | 10/10 | 8/10 | 8/10 |
| - HSM-backed CA | ✅ CloudHSM | ✅ CloudHSM | ✅ CloudHSM |
| - Audit trail | Full (Vault + ESO) | Git + Vault | CloudTrail |
| **TCO 3-Year (15%)** | $0.9M | $0.6M | $0.5M |
| **WEIGHTED SCORE** | **9.2** | **7.6** | **6.1** |

### **Recommendation: External Secrets Operator + Vault (per Security Domain)**
**Rationale**: Only solution supporting hierarchical Security Domains with dynamic secrets, policy-driven rotation, and multi-cloud/hybrid/air-gapped deployment models.

---

## 7. Observability: Thanos/Loki/Tempo/Grafana vs Datadog vs New Relic vs Elastic

| Criterion | **Thanos/Loki/Tempo/Grafana (OSS)** | Datadog | New Relic | Elastic Cloud |
|-----------|---|---|---|---|
| **Technical Fit (25%)** | 9/10 | 9/10 | 8/10 | 8/10 |
| - Metrics (PromQL) | ✅ Thanos | ✅ | ✅ | ✅ |
| - Logs (LogQL) | ✅ Loki | ✅ | ✅ | ✅ |
| - Traces (TraceQL) | ✅ Tempo | ✅ | ✅ | ✅ |
| - Exemplars (trace↔metrics) | ✅ Native | ✅ | ✅ | ⚠️ |
| - Security dashboards (5) | ✅ Buildable | ✅ Built-in | ✅ Built-in | ⚠️ Buildable |
| - SLO-based alerting | ✅ Prometheus rules | ✅ SLOs | ✅ SLOs | ✅ |
| **Operational Maturity (20%)** | 7/10 | 10/10 | 9/10 | 8/10 |
| - Managed option | Self-hosted | Fully managed | Fully managed | Managed |
| - Upgrade burden | Medium | None | None | Low |
| **TCO 3-Year (15%)** | $1.2M | $3.6M | $2.7M | $2.1M |
| - Ingest (150TB/mo) | $720K (storage/compute) | $2.4M | $1.8M | $1.5M |
| - License | $0 | $1.2M | $0.9M | $0.6M |
| - Ops (2 FTE) | $480K | $0 | $0 | $0 |
| **Ecosystem (10%)** | 9/10 | 10/10 | 9/10 | 9/10 |
| **WEIGHTED SCORE** | **8.1** | **9.3** | **8.5** | **7.9** |

### **Recommendation: Self-hosted Thanos/Loki/Tempo/Grafana**
**Rationale**: 67% cost savings vs Datadog with full data sovereignty. Exemplar support critical for security investigations. Team has Prometheus expertise. Grafana dashboards as code (Jsonnet) in GitOps. Evaluate managed Grafana Cloud as backup if ops burden exceeds capacity.

---

## 8. GitOps: ArgoCD vs Flux vs Fleet

| Criterion | **ArgoCD (App-of-Apps)** | Flux v2 | Fleet (Rancher) |
|-----------|---|---|---|
| **Technical Fit (25%)** | 9/10 | 8/10 | 6/10 |
| - App-of-Apps pattern | ✅ Native | ✅ Kustomization | ✅ Bundles |
| - Multi-cluster | ✅ Native | ✅ Multi-cluster | ✅ Native |
| - Drift detection + auto-sync | ✅ | ✅ | ✅ |
| - RBAC / SSO | ✅ Dex/OIDC | ✅ OIDC | ✅ Rancher RBAC |
| - Promotion pipeline | ✅ Argo Rollouts | ✅ Flagger | ⚠️ Basic |
| **Operational Maturity (20%)** | 9/10 | 9/10 | 7/10 |
| **TCO 3-Year (15%)** | $0.18M | $0.18M | $0.3M (Rancher) |
| **WEIGHTED SCORE** | **8.8** | **8.5** | **6.5** |

### **Recommendation: ArgoCD App-of-Apps**
**Rationale**: Best promotion pipeline integration (Argo Rollouts), mature multi-tenant RBAC, largest community. SealedSecrets + ESO integration well-documented.

---

## Summary: Selected Stack

| Layer | Selection | Vendor Support |
|-------|-----------|----------------|
| **Service Mesh** | Istio (Tetrate Distro) | Tetrate Enterprise |
| **CNI / Network Policy** | Cilium (Isovalent Enterprise prod) | Isovalent Enterprise |
| **Workload Identity** | SPIRE (self-managed) | Community + Isovalent (Cilium SDS) |
| **Runtime Security** | Falco + Tetragon | Self-managed (8-wk tuning) |
| **Supply Chain** | Tekton + Cosign + Rekor + Kyverno | Self-managed (isolated build clusters) |
| **Secrets** | External Secrets Operator + Vault (per Domain) | Self-managed + CloudHSM |
| **Observability** | Thanos + Loki + Tempo + Grafana | Self-managed (eval Grafana Cloud backup) |
| **GitOps** | ArgoCD App-of-Apps | Self-managed |
| **API Gateway** | Kong (per env: Enterprise prod, OSS staging/dev) | Kong Enterprise (prod) |

---

## Vendor Contract Negotiation Levers

| Vendor | Leverage Points | Target Discount |
|--------|----------------|-----------------|
| **Tetrate** | Multi-year, reference customer, Istio expertise | 20-25% |
| **Isovalent** | Production-only, Cilium + Tetragon, reference | 15-20% |
| **Kong** | 3 envs, Enterprise only prod, multi-year | 25-30% |
| **CloudHSM** | Reserved capacity, 3-year | 15% (standard) |
| **Sigstore/Rekor** | Open source alternative viable, pilot | 20% |

---

## Exit Criteria (Vendor Lock-in Mitigation)

| Vendor | Open Source Core | Migration Path | Exit Cost |
|--------|------------------|----------------|-----------|
| Tetrate Istio | ✅ Full upstream | Switch to upstream Istio | Low (config migration) |
| Isovalent Cilium | ✅ Full OSS | Switch to OSS Cilium | Low (CRD compatible) |
| Kong Enterprise | ✅ OSS Kong | Migrate to OSS + plugins | Medium (plugin parity) |
| CloudHSM | ❌ | Migrate to Vault + HSM | Medium (key ceremony) |
| Sigstore | ✅ Fully OSS | Self-host Rekor/Fulcio | Low |

**Policy**: No vendor feature used without OSS fallback validated in staging.