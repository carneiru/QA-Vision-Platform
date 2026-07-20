# Cost Model
## QA Vision Platform – Security Foundation Evolution

---

## Executive Summary

**Total 6-Month Investment: $2.8M**
- Infrastructure: $1.2M (43%)
- Vendor/Enterprise: $0.29M (10%)
- Personnel: $1.0M (36%)
- Contingency (15%): $0.37M
- **Annual Run Rate: $5.2M**

---

## Infrastructure Costs (6 Months)

| Component | Configuration | Monthly Cost | 6-Month Total | Annual Run Rate |
|-----------|--------------|--------------|---------------|-----------------|
| **SPIRE Clusters** | 3 envs × 3 nodes (r6g.xlarge) | $30,000 | $180,000 | $360,000 |
| **Istio/Cilium/Falco/Tetragon Nodes** | 3 envs × 20 nodes (m6i.2xlarge) | $40,000 | $240,000 | $480,000 |
| **Build Clusters (Tekton, Isolated)** | 3 envs × 10 nodes (c6i.4xlarge, spot 70%) | $50,000 | $300,000 | $600,000 |
| **Observability (Thanos/Loki/Tempo)** | 3 envs, 150TB/mo ingest, 2yr retention | $33,333 | $200,000 | $400,000 |
| **Control Plane (etcd, NATS, Kafka)** | 3 AZs, 9 nodes (r6g.2xlarge) | $25,000 | $150,000 | $300,000 |
| **Kong per Environment** | 3 × Kong Enterprise (prod), OSS (staging/dev) | $21,667 | $130,000 | $260,000 |
| **External Secrets / Vault** | 3 clusters, HSM-backed | $10,000 | $60,000 | $120,000 |
| **GitOps (ArgoCD, SealedSecrets)** | 3 envs, HA | $5,000 | $30,000 | $60,000 |
| **Network (VPC, TGW, WireGuard)** | Multi-cluster mesh, cross-region | $8,333 | $50,000 | $100,000 |
| **Backup/DR** | Cross-region replication, PITR | $6,667 | $40,000 | $80,000 |
| **TOTAL Infrastructure** | | **$230,000** | **$1,380,000** | **$2,760,000** |

*Note: Infrastructure costs include 20% buffer for scaling events*

---

## Vendor/Enterprise Costs (6 Months)

| Vendor | Product | Tier | 6-Month Cost | Annual Cost | Justification |
|--------|---------|------|--------------|-------------|---------------|
| **Isovalent** | Cilium Enterprise | Production only | $100,000 | $200,000 | eBPF kernel updates, enterprise support, L7 policy |
| **Tetrate** | Istio Distro (TID) | Support subscription | $80,000 | $160,000 | FIPS builds, CVEs, upgrade assistance |
| **Sigstore** | Hosted Rekor + Fulcio | Enterprise | $50,000 | $100,000 | SLSA L3 transparency log, keyless signing |
| **CloudHSM / Azure Key Vault** | HSM for SPIRE CA, Cosign | Managed HSM | $60,000 | $120,000 | FIPS 140-2 L3, key custody |
| **Grafana** | Enterprise (IRM, OnCall) | 3 envs | $0 | $0 | OSS sufficient for MVP |
| **Elastic** | Elastic Cloud (optional) | - | $0 | $0 | Using Loki/Tempo OSS |
| **TOTAL Vendor** | | | **$290,000** | **$580,000** | |

---

## Personnel Costs (6 Months)

| Role | Count | Monthly Cost (Loaded) | 6-Month Total | Annual Cost |
|------|-------|----------------------|---------------|-------------|
| **Platform Engineers** | 4 | $140,000 | $840,000 | $1,680,000 |
| **Security Engineers** | 2 | $150,000 | $300,000 | $600,000 |
| **Training/Certification** | - | $8,333 | $50,000 | $20,000/yr |
| **Red Team / Pen Testing** | - | $16,667 | $100,000 | $200,000 |
| **TOTAL Personnel** | 6 | | **$1,290,000** | **$2,500,000** |

*Note: Loaded cost includes benefits, overhead, equipment at 1.4x base salary*

---

## Phase-by-Phase Cost Breakdown

| Phase | Weeks | Infrastructure | Vendor | Personnel | Total |
|-------|-------|----------------|--------|-----------|-------|
| **Phase 1** (Identity Foundation) | 1-4 | $180K | $50K | $210K | **$440K** |
| **Phase 2** (Control Plane + Secrets) | 5-8 | $220K | $40K | $210K | **$470K** |
| **Phase 3** (Certificates + Mesh) | 9-12 | $250K | $80K | $210K | **$540K** |
| **Phase 4** (Network + Runtime) | 13-16 | $280K | $60K | $210K | **$550K** |
| **Phase 5** (Supply Chain + Observability) | 17-20 | $240K | $40K | $210K | **$490K** |
| **Phase 6** (Governance + APIs) | 21-24 | $210K | $20K | $210K | **$440K** |
| **Contingency (15%)** | - | $207K | $44K | $37K | **$370K** |
| **TOTAL** | 24 | **$1.587M** | **$334K** | **$1.297M** | **$2.8M** |

---

## Cost Sensitivity Analysis

| Scenario | Infrastructure | Vendor | Personnel | Total | Delta vs Base |
|----------|----------------|--------|-----------|-------|---------------|
| **Base Case** | $1.38M | $290K | $1.04M | $2.80M | - |
| **+20% Scale** | $1.66M | $290K | $1.04M | $3.08M | +$280K (+10%) |
| **All OSS (no vendor)** | $1.38M | $0 | $1.40M* | $2.87M | +$70K (+2.5%) |
| **Reserved Instances (3yr)** | $0.97M | $290K | $1.04M | $2.39M | -$410K (-15%) |
| **Extended Timeline (30 wk)** | $1.38M | $290K | $1.30M | $3.06M | +$260K (+9%) |

*Additional engineering effort to replace vendor features

---

## Cost Optimization Opportunities

| Opportunity | Effort | Savings (6mo) | Risk |
|-------------|--------|---------------|------|
| Spot instances for build clusters | Low | $100K | Low (interruption handling) |
| Reserved instances for control plane | Medium | $90K | Low (3yr commitment) |
| Consolidate dev/staging SPIRE | Low | $60K | Medium (blast radius) |
| OpenSearch instead of Loki/Tempo | High | $80K | High (migration effort) |
| Self-hosted Rekor (no Sigstore Enterprise) | Medium | $50K | Medium (operational burden) |
| Shared Kong for dev/staging | Low | $40K | Low (config isolation) |

---

## ROI Justification

### Risk Reduction Value
| Risk Category | Annualized Loss Expectation (ALE) | Mitigation Effectiveness | Annual Value |
|---------------|-----------------------------------|-------------------------|--------------|
| Data Breach (PCI/HIPAA) | $4.2M | 85% | $3.57M |
| Supply Chain Attack | $2.1M | 90% | $1.89M |
| Compliance Findings | $800K | 80% | $640K |
| Operational Incidents | $1.2M | 70% | $840K |
| **Total Annual Risk Reduction** | | | **$6.94M** |

**6-Month Investment: $2.8M → Annual Risk Reduction: $6.94M = 248% ROI**

### Compliance Automation Value
- Manual evidence collection: ~2,000 hrs/yr @ $150/hr = $300K/yr
- Automated (85%): ~300 hrs/yr = $45K/yr
- **Annual Savings: $255K**

### Developer Productivity
- Current avg time to secure new service: 2 weeks
- Target with platform APIs: 2 days
- 50 services/yr × 8 days × $1,500/day = **$600K/yr savings**

---

## Budget Approval Framework

| Approval Level | Authority | Threshold |
|----------------|-----------|-----------|
| **Phase Gate** | Platform Engineering Lead | Per-phase budget ($440K-$550K) |
| **Major Vendor** | VP Engineering + CISO | >$50K single vendor |
| **Scope Change** | Steering Committee | >10% phase budget |
| **Contingency Draw** | VP Engineering + Finance | Any amount |
| **Program Total** | CTO + CFO | $2.8M cap |

---

## Monthly Burn Rate Projection

```
Month 1:  $380K  (Phase 1 start, infra provisioning, training)
Month 2:  $420K  (Phase 1 peak, SPIRE clusters, IdP integration)
Month 3:  $460K  (Phase 1→2 transition, Control Plane deploy)
Month 4:  $490K  (Phase 2 peak, Secrets, Vault migration)
Month 5:  $520K  (Phase 2→3, Istio, Cert Manager)
Month 6:  $530K  (Phase 3 peak, mTLS rollout)
Month 7:  $510K  (Phase 3→4, Cilium, ClusterMesh)
Month 8:  $540K  (Phase 4 peak, Runtime security)
Month 9:  $520K  (Phase 4→5, Supply Chain, Observability)
Month 10: $500K  (Phase 5 peak, SLSA, Dashboards)
Month 11: $480K  (Phase 5→6, Threat modeling, Scorecards)
Month 12: $460K  (Phase 6 peak, APIs, Decommission)
```

**Cumulative 12-month: $5.8M (includes run rate continuation)**

---

## FinOps Guardrails

1. **Budget Alerts**: 80% phase budget → warning, 95% → hard stop
2. **Resource Tagging**: All resources tagged with `phase`, `component`, `environment`, `owner`
3. **Monthly Review**: Finance + Platform Lead review actuals vs forecast
4. **Right-Sizing**: Weekly automated recommendations (Kubernetes VPA, EC2 Rightsizing)
5. **Commitment Discounts**: Evaluate Savings Plans monthly, target 30% coverage by Month 3
6. **Vendor Optimization**: Quarterly review of enterprise feature utilization