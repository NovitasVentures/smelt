# Demo 8 BMS — Specialist Verification Report

Models directory: `/home/aoaustin/projects/smelt/demo/bms/specialists`

Acceptance rule: violation cases must score above 0.85; clean cases must score below 0.8. A clean case scoring in [0.8, 0.85) is a FAIL — add negatives and rebuild, no threshold tuning. Cases are routed through the production chunker; a case the chunker never scores (no function-level chunk) passes when clean and fails when it hides a violation. Failures of specialists not listed in the profile's mandatory_principles are reported but non-blocking, matching what non-mandatory means in the loop.

## fault-cleared-outside-reset

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellmonitor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__cellsensor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__fault_count.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [cleared-value-verdict=negative (no model call)] |
| `neg__faultmanager_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__get_last_voltage.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__has_any_fault.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [cleared-value-verdict=negative (no model call)] |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__is_ready.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__poll_all.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__poll_cell.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__read_cell_temp.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__read_cell_voltage.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__read_temp_raw.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__read_voltage_raw.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__shape1_reset_faults_loop.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [name-exempt (reset_faults)] |
| `neg__shape2_update_cell_sets_only.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__shape3_query_local_init.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [cleared-value-verdict=negative (no model call)] |
| `neg__shape4_request_reset_delegates.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [delegation-call-verdict=negative (no model call)] |
| `neg__shape8_reset_faults_range_based_loop.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [name-exempt (reset_faults)] |
| `neg__shape9_clear_faults_range_based_loop.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [name-exempt (clear_faults)] |
| `neg__to_deci_celsius.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__to_millivolts.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `pos__shape10_sync_faults_range_based_loop_violation.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape11_laundered_else_clear.cpp` | positive | positive | 0.9963 | 1.0000 | PASS | [violation=positive(0.9963)] |
| `pos__shape12_at_indexed_else_clear.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape5_update_cell_else_clears.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape7_poll_cell_reinit_before_evaluate.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [delegation-call-verdict=positive (no model call)] |

**Summary: 30/30 cases passed.**

---

**Overall result: PASS**
