# Glossary
## QA Vision Platform – Security Foundation Evolution

---

## A

| Term | Definition |
|------|------------|
| **ADR** | Architecture Decision Record – lightweight document capturing a significant architectural decision with context, decision, and consequences |
| **Air-gapped** | Environment physically/logically isolated from unsecured networks; no direct internet access |
| **Anti-corruption Layer** | DDD pattern: translation layer between bounded contexts preventing domain model leakage |
| **App-of-Apps** | ArgoCD pattern: root Application manages child Applications for declarative multi-component deployment |
| **AuthorizationPolicy** | Istio CRD defining mesh-level authorization rules (ALLOW/DENY) for workload identities |
| **Auto-response** | Automated containment action (isolate pod, kill process, block IP) triggered by runtime detection rule |

---

## B

| Term | Definition |
|------|------------|
| **Bounded Context** | DDD: explicit boundary within which a domain model applies; enables team autonomy |
| **Bootstrap** | SPIRE: initial trust establishment between SPIRE Server and Agent via join token or K8s SA projection |
| **Break-glass** | Emergency access procedure with audit trail and time-limited elevated permissions |
| **Build Cluster** | Dedicated isolated cluster for CI/CD pipelines (Tekton); separate from runtime clusters |

---

## C

| Term | Definition |
|------|------------|
| **CA** | Certificate Authority – issues and manages X.509 certificates; SPIRE acts as CA for workload identities |
| **Cilium** | eBPF-based CNI providing L3/L4/L7 network policy, ClusterMesh, and transparent encryption |
| **CiliumNetworkPolicy** | CRD extending K8s NetworkPolicy with L7 (HTTP/Kafka/gRPC) awareness and FQDN/DNS rules |
| **ClusterMesh** | Cilium feature connecting multiple K8s clusters with cross-cluster network policy and L7 visibility |
| **CNCF** | Cloud Native Computing Foundation – vendor-neutral home for Kubernetes, Prometheus, SPIRE, etc. |
| **Coarse-Grained** | Authorization at namespace/service level (e.g., "frontend can call backend") |
| **Cosign** | Container signing tool supporting keyless (OIDC) signing, transparency logs (Rekor), and verification |
| **CRI** | Container Runtime Interface – K8s plugin interface for container runtimes (containerd, CRI-O) |
| **CRD** | Custom Resource Definition – extends K8s API with custom types (SecurityDomain, WorkloadIdentity, etc.) |
| **CRI-O** | Lightweight container runtime for K8s implementing CRI |
| **CSI** | Container Storage Interface – K8s standard for exposing storage; SPIRE CSI driver mounts SVIDs |
| **CSI Driver** | Plugin implementing CSI; SPIRE CSI driver provides workload SVIDs as mounted files |

---

## D

| Term | Definition |
|------|------------|
| **DANE** | DNS-based Authentication of Named Entities – binds TLS certificates to DNS via TLSA records |
| **Data Plane** | Network proxy layer (Envoy sidecars) handling actual traffic; controlled by Control Plane |
| **Default-Deny** | Zero-trust posture: all traffic blocked unless explicitly allowed by policy |
| **Deployment Ring** | Progressive rollout strategy: canary → staging → prod with automated validation gates |
| **Detached Signature** | Signature stored separately from artifact (e.g., cosign stores sig in registry, not image) |
| **DevSecOps** | Integrating security practices within DevOps pipeline from code to runtime |
| **Drift** | Configuration divergence between desired state (Git) and actual state (cluster) |
| **Dual-Write** | Migration pattern: write to both legacy and new systems simultaneously during transition |

---

## E

| Term | Definition |
|------|------------|
| **eBPF** | extended Berkeley Packet Filter – safe, programmable kernel technology for networking/observability/security |
| **Egress** | Outbound traffic from workload to external destinations; controlled via EgressGateway + DNS Policy |
| **Ephemeral** | Short-lived (e.g., JWT SVIDs with 5min TTL, X.509 SVIDs with 1hr TTL) |
| **ESO** | External Secrets Operator – syncs secrets from external vaults (Vault, AWS Secrets Manager) to K8s |

---

## F

| Term | Definition |
|------|------------|
| **FAIR** | Factor Analysis of Information Risk – quantitative risk model (Loss Event Frequency × Loss Magnitude) |
| **Federation** | SPIRE: trust relationship between trust domains enabling cross-cluster SVID validation |
| **Fine-Grained** | Authorization at RPC/HTTP path level (e.g., "GET /api/users allowed, POST denied") |
| **FIPS** | Federal Information Processing Standards – cryptographic module validation (FIPS 140-2 Level 3 for HSMs) |
| **FQDN** | Fully Qualified Domain Name – used in Cilium DNS Policy for egress control |

---

## G

| Term | Definition |
|------|------------|
| **Gate** | Phase gate – formal review with Go/No-Go decision criteria (validation results, risks, budget) |
| **GitOps** | Operational model: Git as source of truth; ArgoCD continuously reconciles cluster to Git state |
| **gRPC** | High-performance RPC framework using HTTP/2 + Protocol Buffers; used for Security Control Plane API |
| **Grafana** | Observability visualization platform; dashboards for security scorecards, risk trends, SLOs |

---

## H

| Term | Definition |
|------|------------|
| **HA** | High Availability – multi-AZ deployment with automatic failover (SPIRE, etcd, Control Plane API) |
| **Helm** | K8s package manager; used for deploying Istio, Cilium, SPIRE, observability stack |
| **HSM** | Hardware Security Module – FIPS 140-2 L3 certified; protects SPIRE CA root keys, cosign keys |
| **Hubble** | Cilium's observability UI – service map, flow logs, policy verdict visualization |

---

## I

| Term | Definition |
|------|------------|
| **IdP** | Identity Provider – OIDC/SAML provider (Keycloak, Entra ID, Okta); integrated via IdP Adapter abstraction |
| **IdP Adapter** | Abstraction layer normalizing SCIM provisioning, group mapping, MFA config across multiple IdPs |
| **Ingress** | Inbound traffic entry point; Kong API Gateway per environment with per-route policies |
| **Istio** | Service mesh providing mTLS, traffic management, authorization; SDS integration with SPIRE |
| **Istio SDS** | Secret Discovery Service – Istio's gRPC API for fetching certificates/keys from SPIRE via CSI |

---

## J

| Term | Definition |
|------|------------|
| **JWT SVID** | SPIFFE JWT-SVID – short-lived (5min) token for service-to-service auth; audience-bound |
| **JWT** | JSON Web Token – RFC 7519; used for SPIFFE identity tokens and OIDC IdP tokens |

---

## K

| Term | Definition |
|------|------------|
| **K8s** | Kubernetes – container orchestration platform |
| **Keycloak** | Open-source IdP (OIDC/SAML); reference implementation for IdP Adapter |
| **KinD** | Kubernetes in Docker – local multi-node clusters for development/testing |
| **Kong** | API Gateway (Ingress Controller); dedicated per environment (prod/staging/dev) |
| **Kubelet** | K8s node agent managing pods; SPIRE K8s Workload Attestor integrates with kubelet |
| **Kustomize** | K8s-native configuration management (patches, overlays); used with ArgoCD GitOps |

---

## L

| Term | Definition |
|------|------------|
| **L1/L2/L3/L4** | Validation levels: L1=Automated (CI), L2=Manual (staging), L3=Security Review, L4=Stakeholder Acceptance |
| **L3/L4/L7** | OSI layers: L3=Network (IP), L4=Transport (TCP/UDP), L7=Application (HTTP/gRPC/Kafka) |
| **Legacy Shim** | Adapter translating legacy API calls to new platform APIs during migration |
| **Loki** | Log aggregation (Grafana stack); multi-tenant, label-based, integrates with Tempo/Thanos |

---

## M

| Term | Definition |
|------|------------|
| **mTLS** | Mutual TLS – both client and server authenticate via certificates; STRICT mode enforced by Istio |
| **MITRE ATT&CK** | Adversarial tactics/techniques framework; Falco/Tetragon rules tagged with ATT&CK IDs |
| **Mesh** | Service mesh – Istio control plane + Envoy data plane providing security, observability, traffic control |
| **Multi-Cluster** | Multiple K8s clusters (prod/staging/dev or multi-region) connected via ClusterMesh + Istio Primary-Remote |

---

## N

| Term | Definition |
|------|------------|
| **NATS JetStream** | Persistent streaming layer; event bus for Security Control Plane reconcile engine |
| **NetworkPolicy** | K8s native L3/L4 policy (namespace/pod selectors, ports); extended by CiliumNetworkPolicy |
| **Namespace Isolation** | K8s namespace + NetworkPolicy + RBAC + SecurityDomain forming defense-in-depth boundary |

---

## O

| Term | Definition |
|------|------------|
| **OIDC** | OpenID Connect – identity layer on OAuth 2.0; used for IdP integration and cosign keyless signing |
| **OPA** | Open Policy Agent – Rego-based policy engine; being replaced by Kyverno for K8s-native admission |
| **Observability** | Metrics (Prometheus/Thanos) + Logs (Loki) + Traces (Tempo) + Dashboards (Grafana) unified |
| **OpenAPI 3.1** | API specification standard; Security Platform APIs defined with 14 groups, 121+ endpoints |
| **Operator** | K8s controller pattern managing custom resources (SPIRE, Cert-Manager, Kyverno, External Secrets) |

---

## P

| Term | Definition |
|------|------------|
| **PASTA** | Process for Attack Simulation and Threat Analysis – risk-centric threat modeling methodology |
| **PeerAuthentication** | Istio CRD configuring mTLS mode (PERMISSIVE/STRICT) per namespace/mesh |
| **Platform API** | Unified REST/gRPC API for all security capabilities (Identity, Secrets, Certificates, Policy, Runtime) |
| **Policy as Code** | Security policies expressed as version-controlled CRDs (CiliumNetworkPolicy, AuthorizationPolicy) |
| **Pod** | Smallest K8s deployable unit; workload identity attached via SPIRE CSI driver |
| **Provenance** | SLSA: cryptographic proof of build steps (builder identity, source, dependencies) via in-toto attestation |
| **PSP** | Pod Security Policy (deprecated) → replaced by Pod Security Standards + Kyverno admission |

---

## Q

| Term | Definition |
|------|------------|
| **Kyverno** | K8s-native policy engine (validate/mutate/generate); admission controller for SBOM, signatures, PSP |

---

## R

| Term | Definition |
|------|------------|
| **Rekor** | Transparency log (Sigstore) – immutable record of signed artifacts for supply chain verification |
| **RequestAuthentication** | Istio CRD defining JWT validation rules (issuer, audiences, JWKS URI) for inbound requests |
| **RotationPolicy** | CRD defining secret/cert rotation schedule (cron), canary %, grace period, approval workflow |
| **RPO/RTO** | Recovery Point/Time Objective – DR targets for Security Control Plane (etcd, Vault, SPIRE) |
| **Runtime Security** | Falco (syscalls/K8s audit) + Tetragon (eBPF) → correlation → auto-response (isolate/kill/block) |

---

## S

| Term | Definition |
|------|------------|
| **SBOM** | Software Bill of Materials – SPDX/CycloneDX format; generated at build, verified at admit |
| **SCIM** | System for Cross-domain Identity Management – standardized IdP provisioning (users/groups) |
| **SDS** | Secret Discovery Service – Istio ↔ SPIRE integration for workload certificate distribution |
| **SealedSecrets** | Bitnami controller – encrypts secrets for GitOps storage; only target cluster can decrypt |
| **Security Control Plane** | Centralized API + Reconcile Engine + etcd + NATS managing all security CRDs across clusters |
| **Security Domain** | Hierarchical isolation unit (Domain → Namespace → App) mapping to Vault namespace + policies |
| **Security Scorecard** | Daily computed posture score (8 categories, 40+ metrics, weighted) with FAIR risk overlay |
| **Service Mesh** | See "Mesh" |
| **SIDE** | Security Incident Detection Engine – correlation + auto-response logic for runtime threats |
| **Signing Pipeline** | Tekton task: build → syft SBOM → cosign sign → verify → push to registry |
| **SIVD** | **SPIFFE Verifiable Identity Document** – X.509 or JWT SVID proving workload identity |
| **SLSA** | Supply-chain Levels for Software Artifacts – L3: hermetic build + provenance + non-falsifiable |
| **SOC** | Security Operations Center – consumers of runtime alerts, runbook owners |
| **SPDX** | Software Package Data Exchange – SBOM format (ISO/IEC 5962); alternative to CycloneDX |
| **SPIFFE** | Secure Production Identity Framework For Everyone – standard for workload identity (spiffe.io) |
| **SPIRE** | SPIFFE Runtime Environment – implements SPIFFE; Server + Agent + CSI + SDS + Controllers |
| **SSO** | Single Sign-On – human authentication via IdP (OIDC/SAML) integrated through IdP Adapter |
| **STIG** | Security Technical Implementation Guide – DISA hardening benchmarks; mapped in compliance |
| **STRIDE** | Threat modeling mnemonic: Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation |
| **Supply Chain** | End-to-end: Source → Build (SLSA) → Sign (Cosign) → Verify (Admission) → Deploy → Runtime |

---

## T

| Term | Definition |
|------|------------|
| **Tetragon** | eBPF-based runtime security (Cilium subproject); syscall tracing, file integrity, network visibility |
| **Thanos** | Prometheus long-term storage + global query; sidecar + receive + compact + query components |
| **Threat Model** | Structured analysis (STRIDE/PASTA/Attack Trees) expressed as `ThreatModel` CR in GitOps |
| **TLS** | Transport Layer Security – encrypted transport; mTLS adds mutual authentication |
| **Trust Domain** | SPIFFE concept: namespace for identity trust (e.g., `prod.qa-vision.io`, `staging.qa-vision.io`) |
| **TTL** | Time To Live – SVID validity period (X.509: 1hr, JWT: 5min); auto-rotated by SPIRE |

---

## U

| Term | Definition |
|------|------------|
| **Unified API** | Single OpenAPI surface for all security capabilities; replaces fragmented legacy endpoints |
| **User Workload** | Application pods running business logic; distinct from platform/infrastructure workloads |

---

## V

| Term | Definition |
|------|------------|
| **Vault** | HashiCorp Vault – secrets management; legacy system being migrated to SecurityDomain CRD + ESO |
| **Vault Namespace** | Vault isolation unit; mapped 1:1 with SecurityDomain for hierarchical secret management |
| **Verification** | Admission-time: cosign verify signature, SLSA provenance, SBOM match, policy compliance |

---

## W

| Term | Definition |
|------|------------|
| **WAF** | Web Application Firewall – Kong plugin for L7 attack detection (SQLi, XSS, rate limiting) |
| **WireGuard** | Modern VPN protocol; Cilium ClusterMesh encryption for cross-cluster traffic |
| **Workload** | Any running process (pod, VM, bare metal) that can attest identity via SPIRE |
| **WorkloadIdentity** | CRD representing SPIFFE identity + selectors + SVID config + rotation policy for a workload |

---

## X

| Term | Definition |
|------|------------|
| **X.509 SVID** | SPIFFE X.509-SVID – short-lived (1hr) certificate for mTLS; rotated automatically via CSI driver |
| **XDS** | Istio discovery APIs (CDS, EDS, LDS, RDS, SDS) – control plane → data plane config sync |

---

## Y

| Term | Definition |
|------|------------|
| **YAML** | Configuration format for all CRDs, policies, pipelines, threat models; GitOps source of truth |

---

## Z

| Term | Definition |
|------|------------|
| **Zero-Trust** | Security model: never trust, always verify – identity-based auth, default-deny network, continuous validation |
| **ZTNA** | Zero Trust Network Access – identity-aware proxy replacing VPN; implemented via Kong + SPIRE + Istio |

---

*Version: 1.0 | Owner: Platform Lead + Security Lead | Cross-references: ADRs, Migration Plan, API Spec*