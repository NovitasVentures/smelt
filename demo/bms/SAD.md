# Software Architecture Document (SAD): EV Battery Management System — Cell Monitoring and Fault Management
**Standard:** ISO/IEC/IEEE 42010:2011
**Subject:** Safety-Critical Battery Pack Cell Monitoring and Fault Management Architecture
**Version:** 1.0

---

## 1. Introduction and System Context

The Battery Management System (BMS) cell monitoring library is a C++14 firmware
component for electric vehicle battery packs. It acquires per-cell voltage and
temperature measurements, converts raw sensor readings to engineering units,
evaluates them against safety thresholds, records faults, and decides whether the
main pack contactor may remain closed. This document establishes the architectural
constraints that all engineers contributing to the library must observe.

The consequences of architectural erosion in this domain are not stylistic. A fault
that silently un-latches re-closes the contactor on a damaged cell. A threshold
comparison performed in raw ADC counts silently breaks when the sensing hardware
changes. A diagnostic read that mutates fault state hides a fault from the next
observer. Each of these failure modes is invisible to behavioral testing at the
component boundary; each is prohibited by an explicit principle in Section 6.

The system targets automotive microcontroller platforms. Portability across sensing
hardware variants and auditability of the fault path are first-class requirements.

---

## 2. Stakeholders and Concerns

Per ISO 42010, this architecture is designed to address the specific concerns of the
following stakeholders:

| Stakeholder | Concerns |
| :--- | :--- |
| **Embedded Engineer** | Portability across ADC and sensing hardware variants, clarity of layer responsibilities, testability without physical hardware. |
| **System Architect** | Structural integrity of layer boundaries, enforcement of dependency direction, quarantine of raw sensor values inside the acquisition layers. |
| **Integration / Test Team** | Ability to substitute the hardware layer with fakes, deterministic integer arithmetic in the decision path, repeatable fault-injection scenarios. |
| **Functional Safety Engineer** | Auditability of the fault path: faults must latch until explicit reset, diagnostic reads must be side-effect free, contactor decisions must trace to recorded faults only. |

---

## 3. Use Case View (Architectural Drivers)

### UC-1: Nominal Poll Cycle
- **Actor:** Vehicle control unit (periodic scheduler)
- **Flow:**
  1. `BatterySupervisor` (supervision layer) polls each cell.
  2. `CellMonitor` (monitoring layer) acquires raw counts from `CellSensor` (HAL layer), converts them to millivolts and deci-degrees-Celsius, and returns engineering-unit values.
  3. `BatterySupervisor` feeds the converted values to `FaultManager` (monitoring layer), which evaluates them against the safety thresholds.
  4. `BatterySupervisor` caches the converted voltage for diagnostic queries.
- **Constraint:** `BatterySupervisor` must obtain all measurements through `CellMonitor`. It must not access `CellSensor` directly. Raw ADC counts must never cross into the supervision layer.

### UC-2: Overvoltage Detection and Latch
- **Actor:** Safety monitor
- **Flow:**
  1. A cell voltage exceeds the overvoltage threshold during a poll cycle.
  2. `FaultManager` records an `OVER_VOLTAGE` fault for that cell.
  3. `BatterySupervisor` reports the contactor as not permitted to close.
  4. On subsequent poll cycles the cell reads in-range again (intermittent fault: loose sense wire, cell relaxing after transient).
  5. The fault remains recorded. The contactor remains open.
- **Constraint:** A recorded fault persists regardless of subsequent in-range readings. Only an explicit reset (UC-3) may clear it.

### UC-3: Operator-Initiated Fault Reset
- **Actor:** Service technician / diagnostic tool
- **Flow:**
  1. After inspection, the operator issues a reset request.
  2. `BatterySupervisor` forwards the request to `FaultManager`, which clears all recorded faults.
  3. Subsequent poll cycles re-evaluate cells from a clean state.
- **Constraint:** Fault clearing happens only inside the explicitly named reset operation. Diagnostic queries observe fault state; they never modify it.

---

## 4. Logical View (Component Taxonomy)

The system is decomposed into three layers with a strict unidirectional dependency
structure.

1. **Hardware Abstraction Layer (`hal/`):** Owns all hardware-specific code. Provides `CellSensor`, which reads raw integer ADC counts for per-cell voltage and temperature. The HAL is the only layer permitted to reference platform-specific headers or device drivers. Raw counts originate here and are consumed by the monitoring layer only.

2. **Monitoring Layer (`monitoring/`):** Owns conversion and fault evaluation. `CellMonitor` converts raw counts from the HAL into engineering units (millivolts, deci-degrees-Celsius) and validates raw plausibility. `FaultManager` evaluates converted values against safety thresholds and records faults. The monitoring layer depends on the HAL; it does not depend on the supervision layer.

3. **Supervision Layer (`supervision/`):** Owns orchestration and the contactor decision. `BatterySupervisor` drives the poll cycle, caches converted readings, exposes diagnostic queries, and reports whether the contactor may remain closed. The supervision layer depends on the monitoring layer. It must not depend on the HAL.

---

## 5. Process View (System Dynamics)

1. **Acquisition (downward):** Supervision → Monitoring → HAL. Each layer calls the layer below it. No layer calls upward. No cross-layer callbacks: the HAL holds no pointers to monitoring or supervision functions.
2. **Result propagation (upward):** The HAL returns raw counts to Monitoring; Monitoring returns engineering-unit values to Supervision. Return paths carry either a valid result or an error code — never both.
3. **Raw value quarantine:** Raw ADC counts exist only within the HAL and the conversion functions of the monitoring layer. Every value that participates in a threshold decision is an engineering-unit value. See Principle 6.3.
4. **Fault state flow:** Fault state is written by threshold evaluation and by explicit reset — nothing else. Diagnostic queries are read-only observers. See Principles 6.2 and 6.4.

---

## 6. Development View (Architectural Principles)

### 6.1 Principle: Layer Isolation

The dependency direction between layers is fixed and must never be violated.
Specifically:

- `hal/` headers must never be included in `supervision/` source or header files.
- `supervision/` headers must never be included in `hal/` or `monitoring/` source or header files.
- `monitoring/` may include `hal/` headers. `supervision/` may include `monitoring/` headers.

**Guideline:** Determine which layer each source file belongs to by its directory prefix (`hal/`, `monitoring/`, `supervision/`). Inspect the `#include` directives of every file in the codebase. Any file in `supervision/` that includes a header from `hal/` violates this principle, regardless of whether the functionality appears to work correctly. Any file in `hal/` that includes a header from `monitoring/` or `supervision/` violates this principle. This violation is only detectable by examining the dependency graph across multiple files — it is invisible when inspecting any single file in isolation.

**Rationale:** When supervision code depends directly on HAL headers, swapping the sensing hardware requires modifying contactor decision logic — the highest-consequence code in the system. It also defeats the raw value quarantine: a supervision file with HAL access can read raw counts and make decisions on them. Integration tests cannot substitute a fake HAL without also modifying supervision includes.

### 6.2 Principle: Fault Latching Discipline

A recorded fault must persist until an explicit reset operation clears it. Fault
state must never be cleared as a side effect of re-evaluation, polling, or
diagnostic reads.

**Guideline:** Inspect each function body in isolation. Any assignment of a fault-state member variable to its cleared value (`FaultType::NONE`, `false`, `0`) inside a function whose name is not `reset_faults` or `clear_faults` violates this principle. Assigning a fault value (`FaultType::OVER_VOLTAGE`, `FaultType::UNDER_VOLTAGE`, `FaultType::OVER_TEMP`) is permitted in any evaluation function — setting faults is always allowed; clearing them outside a reset function never is. Assignments to local variables, including initializing a local to `FaultType::NONE`, do not violate this principle.

**Rationale:** The natural implementation of threshold evaluation recomputes fault status from the current reading — an `else` branch that writes the cleared value. That implementation un-latches a fault the moment the reading returns in-range. Intermittent faults (a loose sense wire, a cell oscillating around a thermal threshold) are precisely the faults that must latch: they disappear before a technician can observe them, and a self-clearing fault manager re-closes the contactor on a damaged cell. No behavioral test that observes a fault immediately after injection can detect this defect; it appears only in the recovery window that tests rarely exercise.

### 6.3 Principle: Raw Value Quarantine

Decision logic must compare only converted engineering-unit values (millivolts,
deci-degrees-Celsius) against thresholds. Raw ADC counts must never participate in
a threshold comparison outside the HAL and the conversion functions of the
monitoring layer.

**Guideline:** Inspect each function body in isolation. Any comparison between a raw-count identifier (`raw_counts`, `raw_voltage`, `raw_temp`, or any identifier carrying `raw` or `counts`) and a numeric literal or threshold constant, inside a function that is not a conversion function (`to_millivolts`, `to_deci_celsius`) or a HAL read function (`read_voltage_raw`, `read_temp_raw`), violates this principle. Range-plausibility checks on raw counts (for example, rejecting counts outside the ADC's physical range) are the intended job of conversion functions and do not violate this principle when they appear there.

**Rationale:** A threshold baked into the counts domain (`raw > 3440`) is behaviorally indistinguishable from its engineering-unit equivalent (`voltage_mv > 4200`) on today's hardware — and silently wrong on tomorrow's. When the ADC reference voltage, resolution, or divider network changes, every counts-domain comparison breaks with no compiler diagnostic and no failing test. Counts-domain thresholds are also unreviewable: a safety reviewer can verify 4200 mV against the cell datasheet; 3440 counts requires reverse-engineering the conversion. All decisions on interpreted values, never raw state.

### 6.4 Principle: Diagnostic Query Purity

Diagnostic query functions must not modify any member state. A query observes; it
never mutates.

**Guideline:** Inspect each function body in isolation. Any function whose name begins with `get_`, `is_`, or `has_`, or whose name ends with `_count`, that assigns to a member variable (any identifier with the trailing-underscore member suffix — see ADR-004) violates this principle. Assignments to local variables inside a query are permitted. Functions with command names (`update_*`, `poll_*`, `reset_*`, `configure`) are permitted to mutate member state.

**Rationale:** Read-clears-register semantics are a classic hardware idiom and a classic firmware defect when they leak into diagnostic APIs: the first observer to read a fault consumes it, and every subsequent observer — the logger, the telematics uplink, the redundant supervisor — sees a healthy pack. Polling a diagnostic must not change what the next poll sees. This principle also protects the fault latch (6.2): a query that clears fault state violates both.

### 6.5 Principle: Output Parameter Purity

Functions that communicate results via output parameters must not write to those
parameters on error paths.

**Guideline:** A function that accepts a reference output parameter and returns an error code must only assign the output parameter after all error conditions have been ruled out — that is, on the success path only. If the function returns any non-success error code, the output parameter must remain exactly as it was when the function was called. Initializing the output parameter at the top of the function body before checking for errors is a violation of this principle, even if it is later overwritten on the success path.

**Rationale:** Callers that check the return code and branch on failure may still read the output parameter, assuming it was not written. If the output parameter is modified on an error path, the caller reads a stale or zero-initialized value as if it were valid measurement data. Under a no-exceptions constraint (ADR-001), error codes are the sole failure-signaling mechanism, and output parameter discipline is therefore non-negotiable in the measurement path.

---

## 7. Architectural Decision Records (ADRs)

### ADR-001: No C++ Exceptions (`-fno-exceptions`)
- **Decision:** The library is compiled with exceptions disabled. All error communication uses return codes of type `ErrorCode`. No function may throw.
- **Rationale:** Automotive target platforms prohibit exception handling in operational code paths (AUTOSAR C++14 A15-5-3); exception tables impose unacceptable code size on the target microcontrollers. This decision is the direct motivation for Principle 6.5: without exceptions, error codes plus output parameters are the primary signaling mechanism, and their correctness is critical.

### ADR-002: Fixed-Width Integer Types Only
- **Decision:** All integer variables use `<cstdint>` fixed-width types (`int32_t`, `uint8_t`, etc.). Plain `int`, `long`, `short`, and `unsigned` are prohibited.
- **Rationale:** ADC register widths and CAN signal widths are hardware-defined. Platform-dependent integer types introduce silent arithmetic bugs when the library is ported across architectures with different word sizes. Aligns with AUTOSAR C++14 A3-9-1.

### ADR-003: Integer Engineering Units
- **Decision:** All engineering-unit values are integers: cell voltages in millivolts (`int32_t`), temperatures in deci-degrees-Celsius (`int32_t`, one unit = 0.1 °C). No floating point in the measurement or decision path.
- **Rationale:** Integer arithmetic is deterministic across compilers and FPU configurations, cheap on FPU-less targets, and exact for the resolutions involved. It also makes Principle 6.3 structurally checkable: raw counts and engineering units are distinguished by identifier vocabulary, not by type.

### ADR-004: Trailing-Underscore Member Naming
- **Decision:** All private data members end with a trailing underscore (`faults_`, `ready_`, `last_mv_`).
- **Rationale:** State mutation becomes lexically auditable: an assignment to a trailing-underscore identifier is a member mutation, visible in any function body in isolation. This is the enabler for auditing Principle 6.4 and for reviewing fault-state writes under Principle 6.2.

---

## 8. Quality Attributes

- **Safety:** Enforced by Fault Latching (6.2) and Diagnostic Query Purity (6.4). The fault path is monotonic between resets: faults accumulate, are observed without side effects, and clear only on explicit request.
- **Portability:** Enforced by Layer Isolation (6.1), Raw Value Quarantine (6.3), and ADR-002. Porting to a new sensing platform requires a new HAL and, at most, new conversion coefficients — decision logic is untouched.
- **Auditability:** Enforced by 6.3 (thresholds reviewable in datasheet units) and ADR-004 (mutation visible lexically). A safety reviewer can audit the fault path function by function.
- **Testability:** The monitoring layer can be tested with synthetic raw counts (no hardware). The supervision layer can be tested with fake monitoring components. This is only true if Layer Isolation is preserved — a direct `supervision/` → `hal/` dependency breaks both substitution points.
