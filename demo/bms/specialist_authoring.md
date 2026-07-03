# Demo 8 — Crasis Specialist Authoring: Method Inventory and eval_on Plan

Per the discipline in `demo/crasis/specialist_authoring.md`: complete the method
inventory and eval_on examples for every distinct shape BEFORE the first
`crasis build`. Every spec description/trigger/ignore must say "C++ function body"
and contain real C++ syntax (`FaultType::NONE`, `int32_t`, `faults_[cell] =`), or
the synthetic data generator drifts to prose and Python (Demo 7, build 1 failure).

Five specialists run in this demo. Three are new; two are reused from Demo 7 and
must be re-verified against this inventory (not retrained):

| Specialist | Status | Principle |
|---|---|---|
| `fault-cleared-outside-reset` | NEW | SAD 6.2 Fault Latching Discipline |
| `raw-threshold-comparison-in-decision-logic` | NEW | SAD 6.3 Raw Value Quarantine |
| `state-mutation-in-diagnostic-query` | NEW | SAD 6.4 Diagnostic Query Purity |
| `platform-dependent-integer-types` | REUSED (Demo 7, 97.3%, 6/6) | ADR-002 |
| `output-param-written-before-error-check` | REUSED (Demo 7, 95.7%, 6/6) | SAD 6.5 |

All three new concepts are surface-syntax patterns: token co-occurrence within a
single function chunk, conditioned on the function name that the chunker includes
in every chunk text. None requires control-flow ordering (the failure mode that
made `output-param-written-on-error-path` untrainable at BERT-L2 in Demo 7).

---

## Step 1 — Method inventory

Every method the generated implementation will have, from `bms_spec.md`.
Classification key: **V** = violation temptation (the shape the specialist must
catch if the generator produces it), **FP!** = HIGH-RISK false positive (clean, but
structurally similar to a violation — needs explicit negative eval_on coverage),
**c** = clean/uninteresting for that specialist.

| Method | Mutates members? | Returns | P2 latch | P3 raw | P4 query | P6 out-param |
|---|---|---|---|---|---|---|
| `CellSensor::CellSensor()` | init all | — | FP! (ctor init; chunker skips ctors) | c | c | c |
| `CellSensor::configure` | yes (`raw_*_`, `ready_`) | void | c | c | c (command name) | c |
| `CellSensor::read_voltage_raw` | no | ErrorCode + out | c | FP! (bounds check on `cell`) | c | **V** |
| `CellSensor::read_temp_raw` | no | ErrorCode + out | c | FP! | c | **V** |
| `CellSensor::is_ready` | no | bool | c | c | FP! (query, indexes member array) | c |
| `CellMonitor::CellMonitor()` | stores ref | — | c | c | c | c |
| `CellMonitor::to_millivolts` | no | ErrorCode + out | c | **FP!** (raw range check IN conversion fn = clean) | c | **V** |
| `CellMonitor::to_deci_celsius` | no | ErrorCode + out | c | **FP!** | c | **V** |
| `CellMonitor::read_cell_voltage` | no | ErrorCode + out | c | c (passes raw through, no comparison) | c | **V** |
| `CellMonitor::read_cell_temp` | no | ErrorCode + out | c | c | c | **V** |
| `FaultManager::FaultManager()` | init `faults_` to NONE | — | FP! (chunker skips) | c | c | c |
| `FaultManager::update_cell` | yes (`faults_`) | ErrorCode | **V** (else-clears on recovery) | **FP!** (mv threshold compares = clean) / **V** if raw identifiers | c (command name) | c |
| `FaultManager::get_cell_fault` | must not | FaultType | **V** (clears in getter) | c | **V** (read-clears) | c |
| `FaultManager::has_any_fault` | must not | bool | c | c | **FP!** (loops over `faults_`, returns) | c |
| `FaultManager::fault_count` | must not | uint8_t | c | c | **FP!** (local counter `++count` = clean) | c |
| `FaultManager::reset_faults` | yes (`faults_`) | void | **FP!** (clearing loop, reset name = clean) | c | c (command name) | c |
| `BatterySupervisor::BatterySupervisor()` | init cache | — | c | c | c | c |
| `BatterySupervisor::poll_cell` | yes (`last_mv_`, `valid_`) | ErrorCode | c | **V** (raw compare if HAL shortcut taken) | c | c |
| `BatterySupervisor::poll_all` | via poll_cell | ErrorCode | c | c | c | c |
| `BatterySupervisor::get_last_voltage` | must not | ErrorCode + out | c | c | **V** (lazy cache refresh in getter) | **V** |
| `BatterySupervisor::is_contactor_closed` | must not | bool | c | c | FP! (delegating query) | c |
| `BatterySupervisor::request_reset` | no (delegates) | void | **FP!** (reset-flavored name, delegation body, no fault assignment = clean) | c | c (command name) | c |

Note on constructors: `smelt/scorers/chunker.py` skips constructors and destructors,
so ctor initialization never reaches a classifier at runtime. Keep the ctor-shaped
negatives in eval_on anyway — they steer the synthetic data generator away from
treating brace-init of fault members as a violation pattern.

---

## Step 2 — Shape catalogs and minimal pairs

### P2 — `fault-cleared-outside-reset`

**Concept:** a C++ function body that assigns a cleared value (`FaultType::NONE`,
`false`, `0`) to a fault-state member (trailing-underscore identifier containing
`fault`/`latch`) is a violation unless the function name is `reset_faults` or
`clear_faults`. Setting a fault value is always clean. Local variables are always
clean.

| # | Shape | Class |
|---|---|---|
| 1 | Reset function clears fault members in a loop | Clean — **FP!** |
| 2 | Evaluation function sets a fault value on threshold exceedance (no else-clear) | Clean |
| 3 | Query initializes a local `FaultType` to `NONE` | Clean — **FP!** |
| 4 | Reset-flavored name delegates, body contains no fault assignment | Clean |
| 5 | Evaluation function else-clears the fault when reading is in range | **Violation** |
| 6 | Getter clears the fault member after reading it | **Violation** |
| 7 | Poll function unconditionally re-initializes fault members before evaluating | **Violation** |

Minimal pair A — same clearing assignment, only the function name differs:

```cpp
// CLEAN (shape 1): clearing assignment inside a reset-named function
void FaultManager::reset_faults() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}

// VIOLATION (shape 5): the same clearing assignment inside an evaluation function
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) {
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    } else {
        faults_[cell] = FaultType::NONE;  // un-latches on recovery
    }
    return ErrorCode::OK;
}
```

Minimal pair B — same function name, only the assigned value differs:

```cpp
// CLEAN (shape 2): update_cell that only ever sets fault values
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    } else if (voltage_mv < UNDER_VOLTAGE_MV) {
        faults_[cell] = FaultType::UNDER_VOLTAGE;
    } else if (temp_dc > OVER_TEMP_DC) {
        faults_[cell] = FaultType::OVER_TEMP;
    }
    return ErrorCode::OK;
}
```

Local-initializer negative (shape 3) — `FaultType current = FaultType::NONE;` with
no member assignment. Delegation negative (shape 4) — `request_reset` body calling
`fault_manager_.reset_faults();`.

**Fallback if the draft build cannot separate pair A** (name-conditioning too hard):
retreat to "any `FaultType::NONE` member assignment outside reset-named functions"
with heavier reset-body negative sampling, and rewrite trigger/ignore rather than
patching examples (authoring discipline, build-4 rule).

### P3 — `raw-threshold-comparison-in-decision-logic`

**Concept:** a C++ function body that compares a raw-count identifier (`raw_counts`,
`raw_voltage`, `raw_temp`, `*_counts`) against a numeric literal or threshold
constant is a violation unless the function is a conversion (`to_millivolts`,
`to_deci_celsius`) or HAL raw read (`read_voltage_raw`, `read_temp_raw`).
Comparisons of engineering-unit identifiers (`voltage_mv`, `temp_dc`) are always
clean. Index bounds checks (`cell >= CELL_COUNT`) are always clean.

| # | Shape | Class |
|---|---|---|
| 1 | Decision function compares `voltage_mv` / `temp_dc` against named thresholds | Clean — **FP!** |
| 2 | Conversion function range-checks `raw_counts` against `0..ADC_MAX_COUNTS` | Clean — **FP!** |
| 3 | HAL read bounds-checks the `cell` index | Clean |
| 4 | Decision function compares a raw identifier against a bare numeric literal | **Violation** |
| 5 | Decision function compares a raw identifier against a counts-domain constant | **Violation** |
| 6 | Poll function reads raw counts and threshold-checks them before conversion | **Violation** |

Minimal pair — identical comparison structure, only the identifier vocabulary
differs:

```cpp
// CLEAN (shape 1): decision on engineering units
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) {
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    }
    return ErrorCode::OK;
}

// VIOLATION (shape 4): the same decision made in the counts domain
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t raw_counts, int32_t temp_dc) {
    if (raw_counts > 3440) {  // 4200 mV baked into ADC counts
        faults_[cell] = FaultType::OVER_VOLTAGE;
    }
    return ErrorCode::OK;
}
```

In-spec FP trap (shape 2) — this exact body appears in the specification and MUST
classify negative:

```cpp
// CLEAN: raw range validation inside a conversion function
ErrorCode CellMonitor::to_millivolts(int32_t raw_counts, int32_t& out_mv) {
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    out_mv = (raw_counts * 5000) / 4095;
    return ErrorCode::OK;
}
```

Shape-6 violation (supervision shortcut, pairs with the LayerScorer violation):

```cpp
// VIOLATION: poll compares raw counts before any conversion
ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {
    int32_t raw_counts = 0;
    ErrorCode status = sensor_.read_voltage_raw(cell, raw_counts);
    if (status != ErrorCode::OK) {
        return status;
    }
    if (raw_counts > 3440) {
        fault_manager_.update_cell(cell, 9999, 0);
    }
    return ErrorCode::OK;
}
```

### P4 — `state-mutation-in-diagnostic-query`

**Concept:** C++ port of the Demo 6 CQS specialist (the best-verified concept in
the program). A function named `get_*`, `is_*`, `has_*`, or `*_count` that assigns
to a trailing-underscore member identifier is a violation. Assignments to locals
are clean. Command-named functions (`update_*`, `poll_*`, `reset_*`, `configure`)
mutating members are clean. ADR-004 (trailing-underscore members) is what makes
member mutation lexically visible.

| # | Shape | Class |
|---|---|---|
| 1 | `const`-style query loops over a member array and returns a bool | Clean — **FP!** |
| 2 | Query accumulates into a local (`++count`) and returns it | Clean — **FP!** |
| 3 | Query indexes a member array and returns the element | Clean — **FP!** |
| 4 | Delegating query returns `!fault_manager_.has_any_fault()` | Clean |
| 5 | Command function mutates members (non-query name) | Clean |
| 6 | Getter clears the member it reports (read-clears) | **Violation** |
| 7 | Getter updates a bookkeeping member (`read_count_++`, lazy cache refresh) | **Violation** |

Minimal pair — same iteration-and-return structure; the violation adds exactly one
member assignment:

```cpp
// CLEAN (shape 1): query iterates member state, mutates nothing
bool FaultManager::has_any_fault() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            return true;
        }
    }
    return false;
}

// VIOLATION (shape 6): read-clears — the query consumes the fault it reports
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    FaultType result = faults_[cell];
    faults_[cell] = FaultType::NONE;
    return result;
}
```

Local-counter negative (shape 2) — must classify negative despite the `++`:

```cpp
// CLEAN: local accumulation inside a query
uint8_t FaultManager::fault_count() {
    uint8_t count = 0U;
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            ++count;
        }
    }
    return count;
}
```

Shape-7 violation (bookkeeping mutation — subtler than read-clears):

```cpp
// VIOLATION: getter refreshes the cache member it should only read
ErrorCode BatterySupervisor::get_last_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t mv = 0;
    if (monitor_.read_cell_voltage(cell, mv) == ErrorCode::OK) {
        last_mv_[cell] = mv;  // query mutates cache state
    }
    out_mv = last_mv_[cell];
    return ErrorCode::OK;
}
```

Note: shape 6 violates both P4 and P2. Overlapping same-direction pressure is safe
(Demo 4b, finding 9) — both specialists push the generator toward the same fix.

### Reused specialists — re-verification shapes

`platform-dependent-integer-types` and `output-param-written-before-error-check`
were trained on Demo 7's sensor vocabulary. Before enabling, run `crasis classify`
on every method in the Step 1 inventory. New shapes they have not seen:

- `get_cell_fault` — value-return query with no output parameter (must be negative
  for `output-param-written-before-error-check`)
- `fault_count` returning `uint8_t` from a local accumulator (must be negative for
  both)
- `update_cell` — three-branch threshold ladder with no output parameter (negative
  for `output-param-written-before-error-check`)
- `poll_all` — loop of ErrorCode-returning calls (negative for both)

If any clean method scores above 0.80, demote that specialist from
`mandatory_principles` in `demo8_bms.toml` (keep it in `active_specialists`) and
note it in the build history below.

---

## Step 3 — Verification checklist (before `smelt run`)

1. After `arch-build`, confirm each new specialist directory contains a `.onnx`
   file. A missing export means the build failed silently (Demo 7, build 1).
2. Run `crasis classify` on every shape in every catalog above, plus every method
   body from the Step 1 inventory written out in full.
3. Acceptance at `confidence_threshold = 0.85`: every violation scores above 0.85;
   every clean shape scores below 0.80. A clean shape between 0.80 and 0.85 is a
   build failure — add negatives and rebuild; do not tune the threshold to the
   test set.
4. Budget: 2 builds per specialist (draft + verified), 3 for
   `fault-cleared-outside-reset` (name-conditioning is the hardest concept here).
   On build 4+, rewrite trigger/ignore language instead of patching examples.
5. Re-verify the two reused specialists per the shapes above before granting them
   mandatory status.

## Build history

| Specialist | Build | Result | Root cause / fix |
|---|---|---|---|
| — | — | — | (no builds yet — concept phase) |
