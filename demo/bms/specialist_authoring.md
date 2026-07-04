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
| `fault-cleared-outside-reset` | 0 | spec authored, build pending G1 | Spec written to `demo/bms/specs/fault-cleared-outside-reset.yaml`; 15 eval_on entries (9 clean-tagged / 11 violation-tagged, incl. overlap-with-P4 shape); description/trigger/ignore rewritten with explicit C++ tokens per SAD 6.2. |
| `raw-threshold-comparison-in-decision-logic` | 0 | spec authored, build pending G1 | Spec written to `demo/bms/specs/raw-threshold-comparison-in-decision-logic.yaml`; 13 eval_on entries (8 clean-tagged / 11 violation-tagged, incl. in-spec FP trap for `to_millivolts`/`to_deci_celsius`); description/trigger/ignore rewritten per SAD 6.3. |
| `state-mutation-in-diagnostic-query` | 0 | spec authored, build pending G1 | Spec written to `demo/bms/specs/state-mutation-in-diagnostic-query.yaml`; 14 eval_on entries (10 clean-tagged / 8 violation-tagged); description/trigger/ignore rewritten per SAD 6.4. `output-param-write-on-error.yaml` (arch-import artifact, control-flow framing proven untrainable at BERT-L2 in Demo 7) deleted — principle is covered by the reused `output-param-written-before-error-check` model. |
| `platform-dependent-integer-types` | 1 (BMS-vocabulary retrain) | spec authored for BMS-vocabulary retrain after T4a reuse failure, build pending | T4a reused Demo 7 model passed 22/28 (all 22 clean fixed-width bodies correct, all 6 bare-int violations missed, scoring 0.04-0.50 against the 0.85 gate). Rewrote `demo/bms/specs/platform-dependent-integer-types.yaml` in BMS vocabulary: 28 eval_on entries (22 clean fixed-width Step 1 inventory bodies / 6 bare-int violations — `to_millivolts`, `read_voltage_raw`, `get_last_voltage`, `fault_count`, `update_cell`, `poll_all` — taken verbatim from `demo/bms/verification/cases/platform-dependent-integer-types/`). |
| `output-param-written-before-error-check` | 1 (BMS-vocabulary retrain) | spec authored for BMS-vocabulary retrain after T4a reuse failure, build pending | T4a reused Demo 7 model passed 17/28. Five clean bodies false-positived (`cellsensor_ctor`, `fault_count`, `faultmanager_ctor`, `poll_all`, `reset_faults`, scoring 0.88-0.93) and six write-before-check violations were missed or under-scored (`get_last_voltage`, `read_cell_voltage` sentinel-clobbered, `to_deci_celsius`, `to_millivolts`, `read_temp_raw` init-at-top, `read_voltage_raw` init-at-top, scoring 0.25-0.73 against the 0.85 gate). Rewrote `demo/bms/specs/output-param-written-before-error-check.yaml` in BMS vocabulary: 28 eval_on entries (22 clean / 6 violation) with every one of the above failing cases included verbatim from `demo/bms/verification/cases/output-param-written-before-error-check/`. |
| all 5 specialists | 2 (post crasis 1.3.1 fix) | 0/5 PASS overall; **root cause found in shared infra, not specs** | Diagnosed and fixed a defect in `crasis/factory.py`'s synthetic-data prompt template (generic chat-message scaffold applied even to code specs — see `demo/bms/verification/diagnosis.md`). Filed and merged upstream as crasis-ai/crasis#1 (released 1.3.1). Retrained all 5 against the fix: `platform-dependent-integer-types` 28/28 PASS, `raw-threshold-comparison-in-decision-logic` 25/25 PASS (both first-try), `output-param-written-before-error-check` 23/28 (hit a separate crasis bug — batches truncated mid-JSON at the 4096-token ceiling for this spec's unusually long prompt text; fixed via crasis-ai/crasis#2, `CRASIS_GENERATOR_MAX_TOKENS`, released 1.3.2 — retrained successfully at 23/28 but never revisited after that), `fault-cleared-outside-reset` 12/25, `state-mutation-in-diagnostic-query` 9/22. |
| `fault-cleared-outside-reset`, `state-mutation-in-diagnostic-query` | 3 | `state-mutation-in-diagnostic-query` 22/22 PASS; `fault-cleared-outside-reset` 22/25 | `state-mutation-in-diagnostic-query`: added `read_*` to the permitted command-name prefix allowlist (was missing, causing `read_cell_temp`/`read_cell_voltage` FPs) — fixed cleanly, no regressions. `fault-cleared-outside-reset`: added explicit trigger for "poll function calls the real `reset_faults()` then evaluates" (previous round's eval_on used a differently-named clearing helper) and replaced the broad "generate unrelated code" ignore framing with named concrete contrasts for residual FP clusters (`fault_count`, `has_any_fault`, `is_contactor_closed`, ctors, `to_millivolts`/`to_deci_celsius`). Fixed those FPs but introduced 3 new/residual ones: `neg__poll_cell` FP (a `poll_cell` variant *without* `reset_faults()`, apparently confused with the violation variant that has it), `neg__shape2_update_cell_sets_only` FP (regressed), `pos__shape6_get_cell_fault_read_clears` borderline miss (0.8325 vs 0.85 gate). |
| `fault-cleared-outside-reset` | 4 (final) | 23/25 — **not converging, oscillating** | Made the reset_faults-then-evaluate trigger explicit that the LITERAL call must be textually present (not just any `update_cell`-calling poll function), added a direct clean/violation contrast pair for the two `poll_cell` variants, strengthened the shape2 and read-clears (shape6) examples. Result: all 3 round-3 targets fixed (`poll_cell`, `shape2`, `shape6` all now pass), but 2 *previously-passing* violations broke: `pos__shape5_update_cell_else_clears` (else-branch clearing, now missed) and `pos__shape7_poll_cell_reinit_before_evaluate` (the `reset_faults()`-then-evaluate case itself, now missed — likely over-corrected by the "literal call required" emphasis). Net: 23/25, same count as best-case but a different failure pair than any previous round. Build required 3 stall/retry cycles (crasis generation hung ~97% through with idle OpenRouter connections, self-recovered on the 3rd wait — no code fix applied, treated as transient). **Decision: stop iterating.** 4 rounds show oscillation between 2-3 failure clusters (clear-vs-set discrimination, reset-delegation shape) rather than convergence; accepted as final residual gap alongside `output-param-written-before-error-check`'s untouched 23/28. |
