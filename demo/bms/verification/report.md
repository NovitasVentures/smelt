# Demo 8 BMS — Specialist Verification Report

Models directory: `/home/aoaustin/projects/smelt/demo/bms/specialists`

Acceptance rule: violation cases must score above 0.85; clean cases must score below 0.8. A clean case scoring in [0.8, 0.85) is a FAIL — add negatives and rebuild, no threshold tuning. Cases are routed through the production chunker; a case the chunker never scores (no function-level chunk) passes when clean and fails when it hides a violation. Failures of specialists not listed in the profile's mandatory_principles are reported but non-blocking, matching what non-mandatory means in the loop.

## state-mutation-in-diagnostic-query

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__inv_batterysupervisor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_cellmonitor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_cellsensor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_faultmanager_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_poll_all.cpp` | negative | negative | 0.9244 | 0.0756 | PASS |  |
| `neg__inv_poll_cell.cpp` | negative | negative | 0.8733 | 0.1267 | PASS |  |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.9165 | 0.0835 | PASS |  |
| `neg__inv_read_cell_voltage.cpp` | negative | negative | 0.7616 | 0.2384 | PASS |  |
| `neg__inv_read_temp_raw.cpp` | negative | positive | 0.5536 | 0.5536 | PASS |  |
| `neg__inv_read_voltage_raw.cpp` | negative | negative | 0.5547 | 0.4453 | PASS |  |
| `neg__inv_request_reset.cpp` | negative | negative | 0.9260 | 0.0740 | PASS |  |
| `neg__inv_reset_faults.cpp` | negative | negative | 0.9298 | 0.0702 | PASS |  |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.9133 | 0.0867 | PASS |  |
| `neg__inv_to_millivolts.cpp` | negative | negative | 0.8832 | 0.1168 | PASS |  |
| `neg__inv_update_cell.cpp` | negative | negative | 0.8316 | 0.1684 | PASS |  |
| `neg__shape1_has_any_fault_loop.cpp` | negative | negative | 0.9282 | 0.0718 | PASS |  |
| `neg__shape2_fault_count_local_accumulator.cpp` | negative | negative | 0.9169 | 0.0831 | PASS |  |
| `neg__shape3_is_ready_indexes_member.cpp` | negative | negative | 0.9210 | 0.0790 | PASS |  |
| `neg__shape4_is_contactor_closed_delegates.cpp` | negative | negative | 0.9202 | 0.0798 | PASS |  |
| `neg__shape5_configure_command_mutates.cpp` | negative | negative | 0.8634 | 0.1366 | PASS |  |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 0.9218 | 0.9218 | PASS |  |
| `pos__shape7_get_last_voltage_lazy_refresh.cpp` | positive | positive | 0.8785 | 0.8785 | PASS |  |

**Summary: 22/22 cases passed.**

---

**Overall result: PASS**
