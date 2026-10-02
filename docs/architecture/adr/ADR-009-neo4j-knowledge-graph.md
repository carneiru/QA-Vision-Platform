# ADR-009: Select Neo4j for Knowledge Graph Storage

- Status: Proposed (TARGET architecture; reclassified 2026-10-02 — adopt only when the Blueprint's Implementation Status trigger fires; nothing here is deployed)
- Date: 2024-03-04
- Version: 1.0
- Authors: Architecture Team
- Decision Owner: Chief Architect
- Supersedes: None
- Superseded By: None

---

# Context

## Business Problem
As the QEOS platform evolved to include sophisticated knowledge graph capabilities for representing relationships between quality entities, test results, requirements, and other domain concepts, we required a native graph database capable of efficiently storing, querying, and traversing highly connected data. Traditional relational databases proved inefficient for graph traversals, and we required specialized graph capabilities for pattern matching, path finding, and relationship analytics.

## Technical Problem
Evaluating graph databases necessitated consideration of factors including native graph storage, query language expressiveness, traversal performance, scalability, ACID compliance, ecosystem maturity, and operational tooling. We required a database capable of handling complex graph operations efficiently while providing the reliability and features expected of an enterprise platform.

## Architectural Drivers
- Requirement for native graph storage and processing (not relational overlay)
- Need for expressive graph query language (Cypher)
- High performance for graph traversals and pattern matching
- Support for ACID transactions to ensure data consistency
- Horizontal scalability for growing knowledge graphs
- Robust ecosystem for graph algorithms and analytics
- Operational maturity and tooling for administration and monitoring
- Integration capabilities with our technology stack
- Support for visualizing and exploring graph data

## Constraints
- Must integrate with our microservices architecture and polyglot services
- Must be deployable in our containerized environment (Docker/Kubernetes)
- Must interoperate with services written in multiple languages (Go, Python, Node.js)
- Must comply with enterprise security standards
- Must support our data modeling and schema evolution requirements
- Budget and licensing considerations for enterprise deployment
- Team familiarity or willingness to adopt the technology
- Performance requirements for various graph query patterns

## Assumptions
- Organization will invest in Neo4j expertise and tooling
- Existing infrastructure can support Neo4j deployment requirements
- Sufficient learning resources and training are available for teams
- Neo4j's feature set meets our current and foreseeable graph needs
- Long-term support and evolution of Neo4j is assured
- Network and storage infrastructure can support Neo4j requirements
- Data volume and growth projections for knowledge graphs align with Neo4j's capabilities

## Architecture Principles Addressed
- AP-001: Business Capability Alignment - Systems should be organized around business capabilities
- AP-005: Ubiquitous Language - Common language should be shared between domain experts and developers
- AP-006: Asynchronous Communication - Use async patterns for better scalability and resilience
- AP-009: Scalability - Systems should handle increased load through horizontal scaling
- AP-010: Auditability - Business events should be captured for compliance and analysis
- AP-011: Performance - Systems should be responsive and performant under expected loads

## Quality Attributes Involved
- Graph traversal performance
- Data consistency
- Scalability
- Maintainability
- Security
- Query expressiveness

---

# Decision
Select Neo4j 5.12+ as the native graph database for the QEOS platform's knowledge graph storage needs due to its native graph storage engine, expressive Cypher query language, strong ACID compliance, and proven enterprise reliability for graph workloads.

## Scope
This decision applies to all knowledge graph storage needs within the QEOS platform, including but not limited to: requirement traceability matrices, test case relationships, defect root cause analysis graphs, quality asset dependency graphs, and any other highly connected data benefiting from graph representation and traversal.

## Affected Domains
Primarily affects the Quality Intelligence Platform (QIP) and Collaboration domains, with knowledge graph capabilities potentially consumed by other domains: Platform, Execution, Automation, Administration, Marketplace, and Integrations

## Implementation Boundaries
- Neo4j 5.12+ as minimum version for all deployments
- Use of causal clustering for high availability and read scaling (where applicable)
- Cypher as the primary query language for graph operations
- ACID transactions ensuring consistency for graph modifications
- Indexing strategies for node labels and relationship types to optimize query performance
- Constraints for data integrity (unique constraints, property existence, etc.)
- Procedures and functions for reusable graph logic and algorithms
- Security through authentication, authorization, and encryption
- Backup and recovery strategies for graph data
- Monitoring and alerting for database performance and health

---

# Alternatives Considered

## Amazon Neptune
### Pros
- Managed service reduces operational overhead
- Supports both property graph and RDF models
- Integrated with AWS ecosystem
- Pay-as-you-go pricing model
- Eliminates need to manage underlying infrastructure
- Compatible with Apache TinkerPop Gremlin and SPARQL queries

### Cons
- Vendor lock-in to AWS ecosystem
- Less control over configuration and tuning compared to self-managed
- Potential cost at scale compared to self-managed open-source solutions
- Limited hybrid cloud and multi-cloud portability
- Dependency on AWS service availability and quality
- Fewer enterprise-grade features compared to Neo4j Enterprise
- Less mature tooling for graph visualization and exploration
- Limited support for advanced graph analytics compared to Neo4j Graph Data Science

### Decision
Not selected for primary decision (addressed separately)

### Rejected because
While we may use managed graph services like Neptune in specific AWS contexts, the fundamental decision to adopt a native graph database is separate from the deployment model choice. This ADR focuses on technology selection, not whether we self-manage or use managed services. Additionally, Neo4j offers more mature enterprise features, richer ecosystem, and better tooling aligning with our long-term platform strategy.

## JanusGraph
### Pros
- Open-source and freely available
- Supports multiple storage backends (Cassandra, HBase, etc.)
- Integration with Apache TinkerPop Gremlin
- Horizontal scalability through underlying storage systems
- Good integration with big data ecosystems
- Active community under The Linux Foundation

### Cons
- More complex setup and administration due to multiple moving parts
- Performance dependent on underlying storage backend
- Less mature query optimization compared to native graph databases
- Fewer enterprise-grade features and security options
- Limited tooling for graph visualization and exploration
- Less mature ecosystem for graph algorithms and analytics
- Operational complexity managing the storage layer and JanusGraph layer separately
- Fewer managed service offerings from cloud providers

### Decision
Not selected

### Rejected because
While JanusGraph offers flexibility in storage backends, its complexity and less mature ecosystem make it less suitable than Neo4j for our needs, particularly regarding operational simplicity, performance consistency, and enterprise readiness.

## ArangoDB
### Pros
- Multi-model database (document, graph, key-value)
- Single query language (AQL) for all models
- Good performance for mixed workloads
- Strong consistency model
- Active community and regular releases
- Good tooling for administration and monitoring

### Cons
- Graph performance not as strong as native graph databases like Neo4j
- More complex due to multi-model nature
- Less mature ecosystem for graph-specific algorithms and analytics
- Fewer enterprise-grade features compared to Neo4j
- Less intuitive query language for pure graph operations compared to Cypher
- Limited support for advanced graph visualization and exploration
- Smaller community focused specifically on graph databases

### Decision
Not selected

### Rejected because
While ArangoDB offers interesting multi-model capabilities, its graph performance and ecosystem maturity don't match Neo4j's focus on being a premier graph database, which is what we need for our knowledge graph workloads.

## Redis Graph
### Pros
- Extremely fast performance for simple graph operations
- Simple deployment and operational model
- Integrated with Redis ecosystem
- Low latency for basic graph queries
- Good for caching and real-time graph operations

### Cons
- Limited to in-memory datasets (though Redis on Flash extends this)
- Less suitable for large, persistent knowledge graphs
- Fewer advanced graph features and algorithms
- Less mature querying capabilities compared to Neo4j
- Limited transactional guarantees compared to ACID-compliant databases
- Less suitable for complex graph analytics and data science
- Limited tooling for graph administration and monitoring
- Not designed as a primary graph database for enterprise workloads

### Decision
Not selected

### Rejected because
While Redis Graph offers excellent performance for certain use cases, its limitations in persistence, transactional guarantees, and advanced graph features make it unsuitable for serving as the primary knowledge graph database for the QEOS platform.

## OrientDB
### Pros
- Multi-model database (document, graph, key-value, object)
- Good performance for certain workloads
- SQL-like query language
- Active community and regular releases
- Modular architecture allowing component replacement

### Cons
- Graph performance not as strong as native graph databases
- Complexity due to multi-model nature
- Less mature ecosystem for graph-specific features
- Historical stability concerns in some versions
- Fewer enterprise-grade features compared to Neo4j
- Limited tooling for graph visualization and exploration
- Smaller community focused specifically on graph databases
- Less operational maturity for enterprise graph workloads

### Decision
Not selected

### Rejected because
While OrientDB offers multi-model capabilities, its graph performance and ecosystem maturity don't match Neo4j's focus and proven track record in enterprise graph databases, which is what we need for our knowledge graph workloads.

## TigerGraph
### Pros
- High performance for deep link analytics and graph traversals
- Native parallel processing for graph algorithms
- SQL-like query language (GSQL)
- Good for real-time graph analytics
- Strong performance for certain workload patterns

### Cons
- More complex setup and administration
- Licensing model can be complex and expensive
- Less mature tooling for graph visualization and exploration
- Smaller community compared to Neo4j
- Fewer managed service offerings from cloud providers
- Less operational maturity for general-purpose graph databases
- Less flexible schema evolution compared to Neo4j

### Decision
Not selected

### Rejected because
While TigerGraph offers excellent performance for specific graph analytics workloads, its complexity, licensing, and ecosystem maturity make it less suitable than Neo4j for our general-purpose knowledge graph storage needs.

---

# Consequences

## Positive
- Native graph storage engine optimized for graph storage and traversal
- Expressive and powerful Cypher query language for graph operations
- Strong ACID compliance ensuring data consistency for graph modifications
- Excellent performance for graph traversals, pattern matching, and path finding
- Rich ecosystem of graph algorithms (through Neo4j Graph Data Science library)
- Mature tooling for administration, monitoring, and visualization (Neo4j Bloom)
- Horizontal scalability through causal clustering for read scaling and HA
- Strong security features including encryption, authentication, and authorization
- Active community and regular releases with improvements
- Excellent documentation and learning resources
- Strong performance for both transactional and analytical graph workloads
- Support for temporal graph capabilities through Neo4j Temporal
- Extensibility through user-defined procedures and functions
- Integration with data science tools and pipelines
- Support for geospatial capabilities through Neo4j Spatial
- Natural integration with Kubernetes through operators and sidecars

## Negative
- Can be more complex to administer than simpler databases
- Requires careful tuning for optimal performance in certain workloads
- Memory consumption can be high for large page cache settings
- Backup storage requirements can be significant for large graphs
- Complexity of advanced features may require learning investment
- Cluster setup and management requires expertise
- License costs for Neo4j Enterprise Edition (though Community Edition available)
- Less ubiquitous than some databases in certain hosting environments
- Perception of being "specialized" can affect adoption by teams used to relational databases
- Limited support for non-graph workloads compared to multi-model databases

---

# Implementation

## Affected Components/Services
Knowledge Graph Service, Requirement Traceability Service, Test Impact Analysis Service, Root Cause Analysis Service, Quality Asset Dependency Graph Service, Collaboration Graph Service, Integration Impact Analysis Service, any service needing to store and query highly connected data

## Affected Domains
Primarily Quality Intelligence Platform (QIP) and Collaboration domains, with consumption by: Platform, Execution, Automation, Administration, Marketplace, and Integrations domains

## Deployment Implications
- Neo4j cluster deployment (single instance for dev/test, causal cluster for prod)
- Persistent volumes for data storage in Kubernetes environments
- StatefulSets for managing Neo4j cluster members
- Operators (Neo4j) for automated Neo4j management
- Custom resource definitions for Neo4j clusters
- Init containers for database initialization and schema setup
- Sidecar patterns for log shipping, metrics export, or backup agents
- Network policies for secure access to database services
- Secrets management for database credentials and SSL certificates
- Resource requests and limits for CPU, memory, and storage
- Horizontal pod autoscaling for read replicas based on CPU/utilization (where applicable)
- Pod disruption budgets for high availability
- Services for internal service discovery within Kubernetes
- Load balancers or ingress for external access where needed
- Backup solutions (neo4j-admin dump, or custom solutions) for disaster recovery
- Monitoring exporters for Prometheus integration
- Logging aggregation for Neo4j logs
- Graph data science capabilities installation where needed
- Bloom license and deployment for graph visualization where needed
- Spatial and temporal plugin installation where needed
- Apoc plugin installation for extended procedures and functions
- SSL/TLS configuration for encryption in transit
- Authentication and authorization configuration (LDAP, OAuth, etc.)
- Role-based access control for graph data
- Constraint and index setup for data integrity and performance
- Transaction configuration for performance vs. consistency trade-offs
- Page cache and memory configuration optimization
- Log rotation and retention policies
- Upgrade procedures for Neo4j versions
- Clustering configuration for causal clusters
- Read replica configuration for scaling read workloads

## Operational Considerations
- Connection pool sizing and monitoring
- Query performance monitoring and slow query logging
- Index usage monitoring and optimization
- Page cache monitoring and tuning
- Transaction monitoring and deadlock detection
- Backup verification and restore testing
- Security patching and version updates
- Database statistics collection and analysis
- Node and relationship count monitoring
- Schema and constraint management
- Procedure and function management
- Plugin lifecycle management
- Memory usage monitoring and garbage collection metrics
- Cluster health monitoring (for causal clusters)
- Replication lag monitoring (where applicable)
- Performance benchmarking and baseline establishment
- Capacity planning based on data growth and query patterns
- Disaster recovery procedures and regular testing
- High availability failover testing and procedures (where applicable)
- Load testing and performance optimization
- Compliance reporting and audit preparation
- Data archiving and purging strategies
- Graph algorithm performance monitoring
- Visualization tool integration and usage monitoring
- Data science workload monitoring and optimization

## Migration Considerations
- Phase 1: Establish Neo4j infrastructure and tooling standards
- Phase 2: Design initial graph schema based on domain models (node labels, relationship types, properties)
- Phase 3: Implement connection pooling and security standards
- Phase 4: Create graph migration framework and processes (using neomigrate or similar)
- Phase 5: Establish monitoring, logging, and alerting for database health
- Phase 6: Implement backup and disaster recovery procedures
- Phase 7: Set up high availability and clustering configurations
- Phase 8: Implement performance optimization techniques (indexing, query optimization)
- Phase 9: Set up security measures (encryption, authentication, authorization)
- Phase 10: Implement graph data science capabilities where needed
- Phase 11: Set up visualization tools (Neo4j Bloom) where needed
- Phase 12: Implement extended procedures and functions (Apoc) where needed
- Phase 13: Set up spatial and temporal capabilities where needed
- Phase 14: Establish database administration procedures and runbooks
- Phase 15: Plan for ongoing version updates and patching
- Phase 16: Implement data archiving and purging strategies
- Phase 17: Set up compliance reporting and audit preparation procedures
- Phase 18: Plan for graph data lifecycle management and retention policies

---

# Risks

| Risk | Mitigation |
|------|------------|
| Performance degradation under high load | Proper indexing, query optimization, connection pooling, monitoring and tuning |
| Data loss due to backup failures | Regular backup verification, test restores, implement 3-2-1 backup strategy |
| Security vulnerabilities or misconfigurations | Regular security scanning, implement least privilege, encrypt sensitive data |
| Cluster instability affecting availability | Monitor cluster health, implement alerting, use stable cluster configurations |
| Storage exhaustion due to data growth | Monitor storage usage, implement archiving/purging, plan capacity ahead |
| Connection exhaustion from misbehaving services | Implement connection pooling, monitor connections, set reasonable limits |
| Complexity of advanced features requiring expertise | Invest in team training, use managed services where appropriate, leverage community knowledge |
| Upgrade complexity between major versions | Use rolling upgrades for minimal downtime, test thoroughly in staging |
| Plugin compatibility issues | Test plugins in isolation, maintain plugin compatibility matrix, use official plugins |
| Memory pressure affecting GC performance | Monitor memory usage, tune page cache, schedule maintenance windows |
| Deadlocks affecting throughput | Monitor deadlocks, optimize queries and transactions, use statement timeouts |
| Misuse of features leading to data integrity issues | Implement constraints, use transactions, test thoroughly |
| License compliance issues | Verify compliance with Neo4j License, maintain proper attribution for Enterprise features |

---

# Related Decisions
- ADR-001: Adopt Domain-Driven Design
- ADR-002: Adopt Event-Driven Architecture
- ADR-003: Select Kubernetes as Container Orchestrator
- ADR-004: Select Apache Kafka as Event Backbone
- ADR-005: Select Go for Core Infrastructure Services
- ADR-006: Select Python for AI/ML Services
- ADR-008: Select PostgreSQL as Primary Relational Database
- ADR-010: Select Qdrant for Vector Database
- ADR-017: Bounded Context Map and Context Mapping
- ADR-018: Event Sourcing and CQRS Patterns
- ADR-019: Dead Letter Queue Handling
- ADR-020: Service Mesh Adoption

---

# Change Log
| Date | Version | Description |
|------|---------|-------------|
| 2024-03-04 | 1.0 | Initial version |

---

# References
- Neo4j Documentation
- Neo4j Graph Data Science Library Documentation
- Neo4j Bloom Documentation
- Neo4j Spatial and Temporal Documentation
- Neo4j Operations Manual
- Graph Databases — Ian Robinson, Jim Webber, and Emil Eifrem
- Neo4j in Action — Aleksa Vukotic, Nicki Watt, Tareq Abedrabbo, and Jonas Partner
- Learning Neo4j — Rik Van Bruggen and Valentin Mikhaylov
- Mastering Neo4j 4 — Jason Kotchoff
- Neo4j Graph Algorithms — Mark Needham and Amy E. Hodler
- Graph-Powered Machine Learning — Alessandro Negro
- Neo4j Streams Documentation
- APOC Extended Procedures for Neo4j
- Neo4j Kubernetes Operator
- Neo4j Helm Charts
- Neo4j Cloud Deployment Guides
- Neo4j Docker Images
- Neo4j Monitoring and Metrics
- Neo4j Backup and Recovery Guide
- Neo4j Security Manual
- Neo4j Performance Tuning Guide
- Neo4j Clustering Guide
- Neo4j Causal Clustering Documentation
- Neo4j High Availability Guide
- Neo4j Disaster Recovery Guide

---

# Review
Biennial graph database technology review or when evaluating alternative graph database solutions