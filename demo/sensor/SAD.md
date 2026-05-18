# Software Architecture Document (SAD): Embedded Sensor Pipeline
**Standard:** ISO/IEC/IEEE 42010:2011
**Subject:** Safety-Adjacent Embedded Sensor Data Processing Architecture
**Version:** 1.0

---

## 1. Introduction and System Context

The Embedded Sensor Pipeline is a C++14 firmware library for acquiring, processing, and dispatching sensor data in safety-adjacent embedded systems. It reads raw measurements from hardware sensors, applies calibration and filtering, and delivers conditioned values to application-level decision logic. This document establishes the architectural constraints that all engineers contributing to the library must observe.

The system targets microcontroller and SoC platforms where portability across hardware variants is a first-class requirement. Hardware abstraction is therefore a hard architectural boundary, not a convenience.

---

## 2. Stakeholders and Concerns

Per ISO 42010, this architecture is designed to address the specific concerns of the following stakeholders:

| Stakeholder | Concerns |
| :--- | :--- |
| **Embedded Engineer** | Portability across hardware variants, clarity of layer responsibilities, testability without physical hardware. |
| **System Architect** | Structural integrity of layer boundaries, enforcement of dependency direction, traceability of sensor data through the pipeline. |
| **Integration / Test Team** | Ability to substitute hardware layers with fakes during integration testing, deterministic behavior under fault injection. |
| **Safety Reviewer** | Clear separation of hardware access from decision logic, auditability of error propagation, no hidden coupling between layers. |

---

## 3. Use Case View (Architectural Drivers)

### UC-1: Nominal Sensor Acquisition and Dispatch
- **Actor:** Application controller
- **Flow:**
  1. `SensorDispatcher` (application layer) requests a conditioned reading for a given sensor ID.
  2. `SensorProcessor` (processing layer) acquires a raw sample from `SensorDriver` (HAL layer), applies calibration coefficients, and returns a filtered floating-point value.
  3. `SensorDispatcher` compares the conditioned value against a configured threshold and dispatches an output action accordingly.
- **Constraint:** `SensorDispatcher` must obtain all sensor data through `SensorProcessor`. It must not access `SensorDriver` directly.

### UC-2: Sensor Fault and Threshold Exceedance
- **Actor:** Application controller / safety monitor
- **Flow:**
  1. `SensorDriver` returns a hardware fault code (e.g., communication timeout, out-of-range raw value).
  2. `SensorProcessor` propagates the fault to its caller without modifying any output parameter.
  3. `SensorDispatcher` observes the fault code and routes to the appropriate fault handler without reading a stale or undefined sensor value.
- **Constraint:** On any error return, output parameters must be left unmodified so that callers cannot accidentally read a partially-initialized value as valid data.

---

## 4. Logical View (Component Taxonomy)

The system is decomposed into three layers with a strict unidirectional dependency structure.

1. **Hardware Abstraction Layer (`hal/`):** Owns all hardware-specific code. Provides `SensorDriver`, which reads raw integer samples from sensor registers or peripheral buses. The HAL is the only layer permitted to reference platform-specific headers or device drivers.

2. **Processing Layer (`processing/`):** Owns calibration, filtering, and unit conversion. `SensorProcessor` accepts raw samples from the HAL and produces conditioned floating-point values. All numeric transformation logic lives here. The processing layer depends on the HAL; it does not depend on the application layer.

3. **Application Layer (`application/`):** Owns decision logic and output dispatch. `SensorDispatcher` orchestrates acquisition and dispatch for the application. The application layer depends on the processing layer. It must not depend on the HAL.

---

## 5. Process View (System Dynamics)

Data flows unidirectionally downward for acquisition and upward for results:

1. **Acquisition (downward):** Application → Processing → HAL. Each layer calls the layer below it. No layer calls upward.
2. **Result propagation (upward):** HAL returns raw data to Processing; Processing returns conditioned data to Application. Return paths carry either a valid result or an error code — never both.
3. **No cross-layer callbacks:** HAL does not hold pointers to processing or application functions. The dependency graph is a strict directed acyclic graph with a single direction per edge.

---

## 6. Development View (Architectural Principles)

### 6.1 Principle: Layer Isolation

The dependency direction between layers is fixed and must never be violated. Specifically:

- `hal/` headers must never be included in `application/` source or header files.
- `application/` headers must never be included in `hal/` source or header files.
- `processing/` may include `hal/` headers. `application/` may include `processing/` headers.

**Guideline:** Determine which layer each source file belongs to by its directory prefix (`hal/`, `processing/`, `application/`). Inspect the `#include` directives of every file in the codebase. Any file in `application/` that includes a header from `hal/` violates this principle, regardless of whether the functionality appears to work correctly. Any file in `hal/` that includes a header from `application/` violates this principle. This violation is only detectable by examining the dependency graph across multiple files — it is invisible when inspecting any single file in isolation.

**Rationale:** When application code depends directly on HAL headers, swapping the hardware platform requires modifying application logic. This violates the portability guarantee and creates untestable coupling — integration tests cannot substitute a fake HAL without also modifying application includes. The processing layer exists specifically to absorb hardware-specific knowledge so that the application layer remains platform-neutral.

### 6.2 Principle: Output Parameter Purity

Functions that communicate results via output parameters must not write to those parameters on error paths.

**Guideline:** A function that accepts a reference or pointer output parameter and returns an error code must only assign the output parameter after all error conditions have been ruled out — that is, on the success path only. If the function returns any non-success error code, the output parameter must remain exactly as it was when the function was called. Initializing the output parameter at the top of the function body before checking for errors is a violation of this principle, even if it is later overwritten on the success path.

**Rationale:** Callers that check the return code and branch on failure may still read the output parameter, assuming it was not written. If the output parameter is modified on an error path, the caller reads a stale or zero-initialized value as if it were valid data. This is a silent data corruption failure: no exception is thrown, no assert fires, and the corrupt value propagates into downstream logic. Under a no-exceptions constraint (see ADR-001), error codes are the sole mechanism for communicating failure. Output parameter discipline is therefore non-negotiable.

---

## 7. Architectural Decision Records (ADRs)

### ADR-001: No C++ Exceptions (`-fno-exceptions`)
- **Decision:** The library is compiled with exceptions disabled. All error communication uses return codes of type `ErrorCode`. No function may throw.
- **Rationale:** Target platforms include bare-metal microcontrollers where exception handling tables impose unacceptable code size and the unwinding runtime may be unavailable. AUTOSAR C++14 guidelines prohibit exceptions in operational code paths (A15-5-3). This decision is the direct motivation for the output parameter pattern: without exceptions, error propagation through output parameters is the primary signaling mechanism, and its correctness is therefore critical.

### ADR-002: Fixed-Width Integer Types Only
- **Decision:** All integer variables use `<cstdint>` fixed-width types (`int32_t`, `uint8_t`, etc.). Plain `int`, `long`, and `unsigned` are prohibited.
- **Rationale:** Sensor register widths are hardware-defined. Using platform-dependent integer types introduces silent arithmetic bugs when the library is ported across architectures with different word sizes.

---

## 8. Quality Attributes

- **Portability:** Enforced by Layer Isolation (6.1). Application logic is insulated from hardware-specific headers. Porting to a new platform requires only a new HAL implementation.
- **Safety-Traceability:** Enforced by Output Parameter Purity (6.2). Every error path leaves the caller's output state deterministic, preventing silent propagation of undefined values.
- **Testability:** The processing layer can be tested with synthetic raw values (no hardware required). The application layer can be tested with a fake `SensorProcessor` (no HAL required). This is only true if Layer Isolation is preserved — a direct `application/` → `hal/` dependency breaks both substitution points.
