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
| `pos__shape5_update_cell_else_clears.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [cleared-value-verdict=positive (no model call)] |
| `pos__shape7_poll_cell_reinit_before_evaluate.cpp` | positive | positive | 1.0000 | 1.0000 | PASS | [delegation-call-verdict=positive (no model call)] |

**Summary: 29/29 cases passed.**

## output-param-written-before-error-check (non-mandatory)

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellmonitor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9651 | 0.0349 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__fault_count.cpp` | negative | negative | 0.9685 | 0.0315 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__get_cell_fault.cpp` | negative | negative | 0.9688 | 0.0312 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | positive | 0.9224 | 0.9224 | FAIL | clean case scored 0.9224, required < 0.8 |
| `neg__has_any_fault.cpp` | negative | negative | 0.9691 | 0.0309 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.9684 | 0.0316 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9684 | 0.0316 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9682 | 0.0318 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.9629 | 0.0371 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | positive | 0.9180 | 0.9180 | FAIL | clean case scored 0.9180, required < 0.8 |
| `neg__read_cell_voltage.cpp` | negative | positive | 0.6535 | 0.6535 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | positive | 0.8832 | 0.8832 | FAIL | clean case scored 0.8832, required < 0.8 |
| `neg__read_voltage_raw.cpp` | negative | positive | 0.5284 | 0.5284 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.9688 | 0.0312 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.9690 | 0.0310 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | positive | 0.9594 | 0.9594 | FAIL | clean case scored 0.9594, required < 0.8 |
| `neg__to_millivolts.cpp` | negative | positive | 0.9489 | 0.9489 | FAIL | clean case scored 0.9489, required < 0.8 |
| `neg__update_cell.cpp` | negative | negative | 0.9585 | 0.0415 | PASS |  |
| `pos__get_last_voltage_write_before_check.cpp` | positive | positive | 0.9447 | 0.9447 | PASS |  |
| `pos__read_cell_voltage_sentinel_clobbered.cpp` | positive | positive | 0.9646 | 0.9646 | PASS |  |
| `pos__read_temp_raw_init_at_top.cpp` | positive | positive | 0.9643 | 0.9643 | PASS |  |
| `pos__read_voltage_raw_init_at_top.cpp` | positive | positive | 0.9640 | 0.9640 | PASS |  |
| `pos__to_deci_celsius_write_before_check.cpp` | positive | positive | 0.9625 | 0.9625 | PASS |  |
| `pos__to_millivolts_write_before_check.cpp` | positive | positive | 0.9633 | 0.9633 | PASS |  |

**Summary: 23/28 cases passed.** _(failures non-blocking: not in mandatory_principles)_

## platform-dependent-integer-types

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellmonitor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9148 | 0.0852 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__fault_count.cpp` | negative | negative | 0.9213 | 0.0787 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__get_cell_fault.cpp` | negative | negative | 0.9177 | 0.0823 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | negative | 0.9168 | 0.0832 | PASS |  |
| `neg__has_any_fault.cpp` | negative | negative | 0.9177 | 0.0823 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.8703 | 0.1297 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9189 | 0.0811 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9151 | 0.0849 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.8963 | 0.1037 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | negative | 0.9141 | 0.0859 | PASS |  |
| `neg__read_cell_voltage.cpp` | negative | negative | 0.9114 | 0.0886 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | negative | 0.9161 | 0.0839 | PASS |  |
| `neg__read_voltage_raw.cpp` | negative | negative | 0.9137 | 0.0863 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.8616 | 0.1384 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.9193 | 0.0807 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | negative | 0.8871 | 0.1129 | PASS |  |
| `neg__to_millivolts.cpp` | negative | negative | 0.8916 | 0.1084 | PASS |  |
| `neg__update_cell.cpp` | negative | negative | 0.9071 | 0.0929 | PASS |  |
| `pos__fault_count_bare_int.cpp` | positive | positive | 0.9106 | 0.9106 | PASS |  |
| `pos__get_last_voltage_bare_int.cpp` | positive | positive | 0.9108 | 0.9108 | PASS |  |
| `pos__poll_all_bare_int.cpp` | positive | positive | 0.9041 | 0.9041 | PASS |  |
| `pos__read_voltage_raw_bare_int.cpp` | positive | positive | 0.9108 | 0.9108 | PASS |  |
| `pos__to_millivolts_bare_int.cpp` | positive | positive | 0.9054 | 0.9054 | PASS |  |
| `pos__update_cell_bare_int.cpp` | positive | positive | 0.9110 | 0.9110 | PASS |  |

**Summary: 28/28 cases passed.**

## raw-threshold-comparison-in-decision-logic

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__cellsensor_configure_real_shape.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_batterysupervisor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_cellmonitor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_cellsensor_configure.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_cellsensor_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_fault_count.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_faultmanager_ctor.cpp` | negative | unscored | 0.0000 | 0.0000 | PASS | never scored in production (chunker yields no function-level chunk) |
| `neg__inv_get_cell_fault.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_get_last_voltage.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_has_any_fault.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_is_contactor_closed.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_is_ready.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_poll_all.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_poll_cell_spec_correct.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_read_cell_voltage.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_read_temp_raw.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_request_reset.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_reset_faults.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [violation=negative(0.9446)] |
| `neg__shape1_decision_on_engineering_units.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `neg__shape2_conversion_range_check.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [violation=negative(0.9449)] |
| `neg__shape3_hal_bounds_check.cpp` | negative | negative | 0.0000 | 0.0000 | PASS | [gated-out (no trigger pattern)] |
| `pos__shape4_raw_vs_bare_literal.cpp` | positive | positive | 0.9573 | 1.0000 | PASS | [violation=positive(0.9573)] |
| `pos__shape5_raw_vs_counts_constant.cpp` | positive | positive | 0.9519 | 1.0000 | PASS | [violation=positive(0.9519)] |
| `pos__shape6_poll_cell_raw_shortcut.cpp` | positive | positive | 0.9577 | 1.0000 | PASS | [violation=positive(0.9577)] |

**Summary: 26/26 cases passed.**

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
