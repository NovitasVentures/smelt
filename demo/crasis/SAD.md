# Software Architecture Document (SAD): CoffeeLoop
**Standard:** ISO/IEC/IEEE 42010:2011  
**Subject:** Distributed Order Processing Reference Architecture  
**Version:** 1.0  

---

## 1. Introduction and System Context
CoffeeLoop is a distributed order-management system designed to demonstrate robust architectural principles within a microservices ecosystem. It orchestrates the lifecycle of a beverage order from inception to user notification. This document serves as the primary architectural guidance for all engineers contributing to the system.

---

## 2. Stakeholders and Concerns
Per ISO 42010, this architecture is designed to address the specific concerns of the following stakeholders:

| Stakeholder | Concerns |
| :--- | :--- |
| **Developer** | Predictability, ease of debugging, modularity, and "DRY" code maintenance. |
| **Architect** | Structural integrity, separation of concerns, and system-wide consistency. |
| **Operations** | Observability, error propagation, and service uptime. |
| **End-User** | Consistent experience and timely feedback on order status. |

---

## 3. Use Case View (Architectural Drivers)
These scenarios define the primary functional requirements that the architecture must satisfy.

### UC-1: Successful Order Processing
- **Actor:** Customer
- **Flow:** 1. Customer submits order via **Order Gateway**.
    2. **Order Gateway** validates inventory with **Inventory Manager**.
    3. **Inventory Manager** confirms availability.
    4. **Order Gateway** triggers **Notification Service**.
    5. Customer receives confirmation.
- **Constraint:** Transactional integrity between Gateway and Inventory is required.

### UC-2: Resource Exhaustion (Out of Stock)
- **Actor:** Customer / Inventory System
- **Flow:**
    1. **Order Gateway** requests stock check.
    2. **Inventory Manager** returns "Insufficient Resources."
    3. **Order Gateway** notifies the user of the failure via **Notification Service**.
- **Constraint:** The system must remain responsive and provide clear error states.

---

## 4. Logical View (Component Taxonomy)
The system is decomposed into three autonomous applications to ensure a strict separation of concerns.

1.  **Order Gateway:** The central orchestrator. It manages the state machine of an order and enforces business workflow logic.
2.  **Inventory Manager:** The source of truth for physical resources. It provides idempotent operations for checking and reserving ingredients.
3.  **Notification Service:** A message sink responsible for translating system events into human-readable messages (Email/SMS/Push).

---

## 5. Process View (System Dynamics)
This view describes the interaction patterns between components.

1. **Synchronous Request/Response:** Used between the **Order Gateway** and **Inventory Manager** to ensure real-time stock accuracy before proceeding with an order.
2. **Asynchronous Event-Driven:** Used between the **Order Gateway** and **Notification Service**. The Gateway emits an event and immediately returns a response to the user, decoupling user-facing latency from notification delivery.

---

## 6. Development View (Architectural Principles)
To satisfy the **Developer** stakeholder's concern for maintainability and predictability, all components must adhere to these three core principles.

### 6.1 Principle: Single Exit Path (SEiP)
To ensure deterministic execution and simplify the use of debuggers and profilers, all functions must implement a single return point.
- **Guideline:** Initialize a result variable at the top of the function, modify it throughout the logic, and return it exactly once at the final line.
- **Rationale:** Prevents "hidden" logic branches where cleanup code or logging might be bypassed by an early return.

### 6.2 Principle: System-Wide DRY (Shared Core)
Logic that bridges two or more applications must be abstracted into a shared architectural core.
- **Guideline:** Data schemas (e.g., the `Order` object), Error codes, and standard Response envelopes must be imported from the `coffeeloop-core` library.
- **Rationale:** Prevents "Schema Drift" and ensures that all services speak the same dialect.

### 6.3 Principle: Structured Exception Handling
Exceptions must be handled at the boundaries, not swallowed within business logic.
- **Guideline:** - Use specific `try...except` blocks for expected failures (e.g., Network Timeout).
    - Re-wrap low-level errors into a standard system exception before propagating.
    - Every app must have a "Global Error Handler" at the entry point to prevent unhandled crashes and ensure logs are formatted correctly.
- **Rationale:** Maintains observability across the distributed system.

---

### 6.4 Principle: Result Accumulator Pattern (RAP)

All functions that compute and return a value must follow the Result Accumulator Pattern.
- **Guideline:** Declare a single result variable (`result`) as the first executable statement of the function body. Update `result` through the logic. Return `result` exactly once, at the final line. Returning directly from within a conditional branch is prohibited. Raising an exception for a precondition failure is not a return point and does not violate this rule.
- **Rationale:** Predictable exit semantics. When a function has multiple return statements scattered through conditional branches, debuggers and profilers attach to only one of them — the others are invisible to step-through execution. A single accumulator-and-return pattern means every tool that attaches to the return sees every execution.

---

## 7. Architectural Decision Records (ADRs)

### ADR-001: Hybrid Communication Pattern
- **Decision:** Use Synchronous REST for Inventory and Asynchronous Messaging for Notifications.
- **Rationale:** Stock verification is a prerequisite for a valid order (Sync); notification is a side effect (Async). This optimizes for both data consistency and system availability.

### ADR-002: Implementation Language (Python/C++/C)
- **Decision:** Selection depends on the specific performance profile of the service, provided they implement the `coffeeloop-core` interface.
- **Rationale:** By defining the architecture in ISO terms, the language becomes an implementation detail, though Python is preferred for the Gateway to facilitate rapid iteration.

---

## 8. Quality Attributes
- **Maintainability:** High, achieved via SEiP and DRY principles.
- **Testability:** Each component can be mocked using the standardized shared core schemas.
- **Reliability:** Graceful degradation is achieved through structured exception handling at the component boundaries.
