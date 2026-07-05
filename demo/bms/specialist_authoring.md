# Demo 8 — Crasis Specialist Authoring: Method Inventory and eval_on Plan

Per the discipline in `demo/crasis/specialist_authoring.md`: complete the method
inventory and eval_on examples for every distinct shape BEFORE the first
`crasis build`. Every spec description/trigger/ignore must say "C++ function body"
and contain real C++ syntax (`FaultType::NONE`, `int32_t`, `faults_[cell] =`), or
the synthetic data generator drifts to prose and Python (Demo 7, build 1 failure).

Five specialists run in this demo. The original plan reused two Demo 7 models
unchanged; that failed verification (2026-07-03, T4a — the English rules
transferred, the weights didn't), so all five are BMS-vocabulary builds. Status
as of 2026-07-05 (see Build history for the full arc):

| Specialist | Status | Principle |
|---|---|---|
| `fault-cleared-outside-reset` | COMPOSITE: deterministic name-exemption + trigger gate around `fault-clearing-dataflow` (see build 7) | SAD 6.2 Fault Latching Discipline |
| `raw-threshold-comparison-in-decision-logic` | NEW, 25/25 | SAD 6.3 Raw Value Quarantine |
| `state-mutation-in-diagnostic-query` | NEW, 22/22 | SAD 6.4 Diagnostic Query Purity |
| `platform-dependent-integer-types` | Demo 7 rule, retrained on BMS vocabulary, 28/28 | ADR-002 |
| `output-param-written-before-error-check` | Demo 7 rule, retrained, 23/28 — demoted from mandatory (see build history) | SAD 6.5 |

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
| `fault-cleared-outside-reset` | 5 (2026-07-04, single-specialist diagnosis) | ruled out capacity and label quality as root cause | Three targeted rounds: BERT-Tiny→BERT-Mini capacity increase (worse: 24/28, new 98%+-confident wrong-direction failures); label-contradiction fix (found `clear_all_faults` labeled negative 10/10 as its own definition but positive ~80% when called — traced to the fuzzy "or a similar reset-named operation" spec phrase; tightened to exact names; fixed all label contradictions, same 3 violation shapes still failed); vocabulary-rebalance fix (71/78 exact-project-vocabulary examples were negative — added 5 positives; statistically no change). Function-name-level measurement: `update_cell` co-occurs with negative labels 170/217 (78%), `sync_faults` had zero examples of any label. Conclusion: architectural mismatch — one small classifier cannot learn a name-conditioned exemption and an identifier-blind data-flow judgment from naturally generated data. |
| `fault-cleared-outside-reset` | 6 (2026-07-04, composite v1) | 9/9 on hand-picked hard cases; 21/28 full suite across 2 rounds | Split into `reset-name-exemption` (BERT-Tiny, name check on raw text) + `fault-clearing-dataflow` (BERT-Mini, data-flow on identifier-redacted text), AND-NOT combined in `crasis_scorer.py`. All 3 chronic violation shapes fixed, but the dataflow specialist false-positived on read-only/pass-through shapes it had no negatives for (`has_any_fault`, `read_cell_temp`/`read_cell_voltage`, `shape3`); round-2 negatives fixed `has_any_fault` but regressed `shape7` — the oscillation relocated into the dataflow model. Also fixed en route: the member-redaction regex could not match multi-underscore identifiers (`fault_manager_`), silently leaving real member names in round-1 "redacted" training data. |
| `fault-cleared-outside-reset` | 7 (2026-07-05, hybrid decomposition) | 27/28 BEFORE any retrain; round-3 retrain fixed `shape7`, introduced a new FP | Compiled the rule's deterministic clauses out of the model: `exemption_signatures` (exact-name string check against the chunk signature — retired the `reset-name-exemption` BERT, a neural network doing string comparison) and `trigger_patterns` (member assignment / member range-loop / clearing-idiom call; chunks matching none are structurally incapable of clearing and never reach the model). `verify.py` now routes cases through the production chunker (the 3 ctor "failures" were harness artifacts — production skips ctors). Two root causes found for the `shape7` residual: (1) redaction erased reset/clear call names, making "delegates to a clearing routine" and "delegates to anything else" identical text with opposite labels — the eval_on set contained that literal contradiction, byte-identical examples labeled both ways; fixed with `redaction_preserve_prefixes` (rule vocabulary survives redaction). (2) crasis tokenized at max_length=128 at train AND inference while chunks run to 512 — `shape7`'s redacted text is 193 tokens and its `reset_faults()` call sits past token 128: the model literally never saw the violation, in training or inference (diagnosis.md root cause 2, recommended 2026-07-03, never applied). Fixed as crasis c113355 (1.4.0, `CRASIS_MAX_SEQUENCE_LENGTH`, default 512). Spec narrowed: cleared value is `FaultType::NONE` only (bool/int forms are indistinguishable from benign flag writes once redacted — FP amplifier per diagnosis.md); delegation judged via preserved reset/clear tokens (bare wrapper = clean, clearing call + further work = reinit violation). Retrain fixed `shape7` (27/28) but introduced a new FP: `neg__poll_cell` (the exact minimal-pair negative — same body as `shape7` minus the `reset_faults()` call) now scores 0.9891 positive. |
| `fault-cleared-outside-reset` | 8 (2026-07-05, minimal-pair refinement, same round) | 27/28, unchanged — FP confidence increased (0.9891 → 0.9953) | Added the exact `neg__poll_cell` shape to eval_on as a negative, reasoning the model lacked its precise minimal-pair contrast. Measured the actual training data instead of re-guessing: among 1236 examples containing a bare `reset_faults()`/`clear_faults()` CALL (as opposed to a `CLASS::reset_faults()` DEFINITION), 81% (1004/1236) are labeled positive — the generator produces far more "reinit-before-evaluate" positives than "pure delegation" negatives for this call-shape, because the spec's trigger clause describes the positive pattern in much more detail than the negative one. One added example cannot shift a systemic 81/19 skew baked into 1236 generated examples — the identical failure mode documented in build 5 (function-name-level correlation) and build 6 (composite round 2), now in a third location. **Decision: stop iterating per the plan's one-retrain budget and stated stop condition.** The minimal-pair eval_on addition was removed from the spec (statistically inert against a systemic skew, and adding training-data noise for no benefit), but the model in place is the round-3 build (27/28, `neg__poll_cell` FP) — synthetic generation is non-deterministic, so a bare rebuild would not reliably reproduce or improve on this result, and re-running training would spend a 4th round's budget for an uncertain outcome. `neg__poll_cell` is retained as a documented known gap alongside `output-param`'s. It is not one of the four money-moment shapes (else-clears, read-clears, range-loop-outside-reset, reinit-before-evaluate) and has not appeared in generated BMS code observed in prior smelt runs. A real fix would need the trigger/ignore text rebalanced to describe the negative delegation shape at equal length/specificity to the positive reinit shape, or a much heavier (15-20+) negative-example weighting — deferred, not attempted this session. **User decision (2026-07-05, AskUserQuestion): accept and proceed to the end-to-end run.** `neg__poll_cell` documented as a known, root-caused gap; not demoted from `mandatory_principles` (unlike `output-param`) because it does not affect the four money-moment shapes the demo depends on, and demoting SAD 6.2 — the demo's headline principle — would undercut the central architectural-violation narrative. Risk accepted: a generated implementation producing this exact narrow shape (two read-delegate calls then member array writes, no clearing call, no reset call) would be flagged as a false violation; this shape has not appeared in any prior BMS run. |
| `output-param-written-before-error-check` | — (2026-07-05, demoted) | 23/28; removed from `mandatory_principles`, kept in `active_specialists` | Applied the pre-committed demotion policy (profile comment: imperfect clean/violation separation → demote, keep active, record here). Its 5 false positives (`get_last_voltage`, `read_cell_temp`, `read_temp_raw`, `to_deci_celsius`, `to_millivolts`) sit on core spec-API conversion/read functions the converged implementation must contain — as a mandatory principle it made CONVERGED structurally unreachable. The 2026-07-04 status report mistakenly tabled it as "clean (reused from Demo 7)", which hid this for a session; it has been 23/28 since the build-2 retrain and was never revisited. Still scores and appears in the trace; can no longer block. Revisit after the end-to-end run. |
| `raw-threshold-comparison-in-decision-logic` | — (2026-07-05, gate-only composite) | 25/25 → 26/26, both `configure` shapes gated out | The 2026-07-05 end-to-end run found a real FP: `CellSensor::configure` (pure assignment via `.at(cell)`, zero comparison operators) scored 0.9476 positive — vs 0.7081 for the already-verified `[]`-indexed variant of the identical logic. Direct `classify()` isolated the cause to indexing-style surface pattern, not the comparison the rule's own trigger clause requires ("compares a raw-count identifier ... against a numeric literal or threshold constant"). Converted to a **gate-only composite** — `trigger_patterns` requiring an actual comparison operator (`>`,`<`,`>=`,`<=`,`==`,`!=`) adjacent to a raw/counts-flavored identifier, **no exemption tier** (relaxed `_score_composite`'s "exactly one of exemption_specialist/exemption_signatures" to "at most one, but at least one of the three mechanisms" — a rule with no separate "is this permitted" question needs only a gate, the model verdict is final once gated in). Assignment-only bodies never reach the model; the existing conversion-function name judgment (25/25) is untouched since real comparisons — including `to_millivolts`'s own raw-range check — still gate in and classify exactly as before. Added `neg__cellsensor_configure_real_shape.cpp` (the exact `.at()` shape) to the verification suite. |
| `fault-cleared-outside-reset` | 9 (2026-07-05, full deterministic resolution) | **28/28 — first clean pass in this composite's history** | Both build-8's accepted `neg__poll_cell` gap AND a newly-surfaced `neg__shape3_query_local_init` FP (see below) resolved by recognizing that both were structural-shape questions with no data-flow content left after redaction — i.e. genuinely unlearnable by design, not merely hard for this training run. Added two new deterministic tiers, `delegation_call_patterns` and `cleared_value_patterns`, checked on the ORIGINAL (unredacted) chunk before any model call: (1) `_delegation_call_verdict` — a reset/clear-prefixed call alone in the body is clean delegation; the same call followed by further work is reinit-before-evaluate (fixes `neg__poll_cell`, whose only textual difference from the `pos__shape7` violation is the presence of that one call). (2) `_cleared_value_assignment_verdict` — `FaultType::NONE` assigned to a trailing-underscore member (direct/indexed/range-loop) is a violation; assigned to a local variable, or appearing only in a comparison, is not (fixes `neg__shape3_query_local_init`, surfaced only after the `trigger_patterns` fix above started letting local-`FaultType::NONE` chunks reach the model at all). Both checks return an AUTHORITATIVE verdict in both directions once the trigger gate has already established the chunk is in-scope — a subtle point that caused one real bug during implementation: `verify.py`'s harness treated a `False` cleared-value verdict as "fall through to the model" instead of "clean, stop," which silently let `shape3` keep failing after the scorer-side fix already worked; fixed by mirroring the scorer's own authoritative-False handling. Verified against all 28 cases: **the deterministic stack alone resolves every case except one constructor shape the production chunker filters out before it reaches any scorer** — i.e., matching or exceeding 8 build rounds' worth of model accuracy with zero model calls. The `fault-clearing-dataflow` model is kept wired as a fallback for any chunk neither deterministic tier resolves (none currently exist in the known shape catalog) rather than retired outright, since a generated codebase can still produce a shape the hand-authored suite hasn't anticipated. **Overall verification result: PASS for the first time this session** (previously blocked by this rule and/or `output-param`). |
