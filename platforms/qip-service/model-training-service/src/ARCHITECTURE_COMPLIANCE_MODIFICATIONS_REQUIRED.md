# Architecture Compliance - Required Modifications

## Architecture Blueprint v1.0 - WARNING (Mostly Compliant)

**Issue 1: Write Ownership Principle**
- **Reference**: Architecture Blueprint v1.0, Section 5.3 (Data Management Principles)
- **Problem**: Some direct database access in service layer that could be better encapsulated through repository patterns
- **Exact Modification Required**: 
  - Move all direct SQLAlchemy queries from service layer to repository implementations
  - Ensure all data access goes through the ModelRepository interface
  - Update ModelService to use repository methods instead of direct database session operations

**Issue 2: Event-Driven Pattern Consistency**
- **Reference**: Architecture Blueprint v1.0, Section 4.2 (Event-Driven Communication)
- **Problem**: Not all cross-domain communication follows the event-driven pattern
- **Exact Modification Required**:
  - Ensure all inter-service communication happens exclusively through Kafka events
  - Remove any direct HTTP calls to other services
  - Implement event handlers for incoming events from other domains

## ADR-001 (Domain-Driven Design) - WARNING (Mostly Compliant)

**Issue 1: Business Logic in Service Layer**
- **Reference**: ADR-001, Section 3.2 (Domain Layer Responsibilities)
- **Problem**: Some business logic resides in application/services rather than domain entities
- **Exact Modification Required**:
  - Move business logic from ModelService methods into Model entity methods
  - Examples:
    - Model validation logic should be in Model entity
    - State transition rules should be encapsulated in Model entity
    - Business rules for model deployment/evaluation should be in domain layer
  - Refactor ModelService to act as a true application service that orchestrates domain objects

**Issue 2: Anemic Domain Model**
- **Reference**: ADR-001, Section 3.1 (Domain Model Characteristics)
- **Problem**: Domain models are primarily data containers with limited behavior
- **Exact Modification Required**:
  - Add behavior methods to Model entity that encapsulate business rules
  - Implement methods like:
    - `can_transition_to_status(new_status)` - encapsulates state transition rules
    - `is_ready_for_deployment()` - encapsulates deployment readiness logic
    - `validate_training_config(config)` - encapsulates validation rules
  - Move validation and business rule enforcement from service methods to entity methods

## ADR-018 (Event Sourcing and CQRS) - WARNING (Partially Compliant)

**Issue 1: Missing Event Store**
- **Reference**: ADR-018, Section 2.3 (Event Sourcing Implementation Requirements)
- **Problem**: No mechanism to persist events as the source of truth
- **Exact Modification Required**:
  - Implement an EventStore interface and implementation
  - Create event tables in database to store all domain events
  - Modify repository to save events to event store alongside entity state
  - Implement event replay capability to rebuild entity state from events

**Issue 2: Incomplete CQRS Separation**
- **Reference**: ADR-018, Section 3.1 (CQRS Pattern Implementation)
- **Problem**: Read and write operations are not fully separated
- **Exact Modification Required**:
  - Separate read (query) and write (command) models
  - Create query handlers that are distinct from command handlers
  - Implement read model projections that update from event stream
  - Separate API endpoints for queries vs commands if beneficial
  - Consider implementing query-specific data structures optimized for reading

**Issue 3: Missing State Reconstruction from Events**
- **Reference**: ADR-018, Section 2.4 (Event Sourcing Benefits)
- **Problem**: No ability to rebuild current state from event history
- **Exact Modification Required**:
  - Implement event handlers that can rebuild entity state
  - Add functionality to replay events for a specific entity to reconstruct its current state
  - Ensure all state changes are derived exclusively from events