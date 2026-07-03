# Demo 8 BMS — Specialist Verification Report

Models directory: `/home/aoaustin/projects/smelt/demo/bms/specialists`

Acceptance rule: violation cases must score above 0.85; clean cases must score below 0.8. A clean case scoring in [0.8, 0.85) is a FAIL — add negatives and rebuild, no threshold tuning.

## fault-cleared-outside-reset

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | positive | 0.9360 | 0.9360 | FAIL | clean case scored 0.9360, required < 0.8 |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.9097 | 0.0903 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | positive | 0.9512 | 0.9512 | FAIL | clean case scored 0.9512, required < 0.8 |
| `neg__cellsensor_ctor.cpp` | negative | positive | 0.9545 | 0.9545 | FAIL | clean case scored 0.9545, required < 0.8 |
| `neg__fault_count.cpp` | negative | positive | 0.5685 | 0.5685 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.9063 | 0.0937 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | positive | 0.9592 | 0.9592 | FAIL | clean case scored 0.9592, required < 0.8 |
| `neg__has_any_fault.cpp` | negative | positive | 0.7139 | 0.7139 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.9356 | 0.0644 | PASS |  |
| `neg__is_ready.cpp` | negative | positive | 0.9414 | 0.9414 | FAIL | clean case scored 0.9414, required < 0.8 |
| `neg__poll_all.cpp` | negative | positive | 0.9516 | 0.9516 | FAIL | clean case scored 0.9516, required < 0.8 |
| `neg__poll_cell.cpp` | negative | positive | 0.9568 | 0.9568 | FAIL | clean case scored 0.9568, required < 0.8 |
| `neg__read_cell_temp.cpp` | negative | positive | 0.9598 | 0.9598 | FAIL | clean case scored 0.9598, required < 0.8 |
| `neg__read_cell_voltage.cpp` | negative | positive | 0.9592 | 0.9592 | FAIL | clean case scored 0.9592, required < 0.8 |
| `neg__read_temp_raw.cpp` | negative | positive | 0.9600 | 0.9600 | FAIL | clean case scored 0.9600, required < 0.8 |
| `neg__read_voltage_raw.cpp` | negative | positive | 0.9588 | 0.9588 | FAIL | clean case scored 0.9588, required < 0.8 |
| `neg__shape1_reset_faults_loop.cpp` | negative | negative | 0.8662 | 0.1338 | PASS |  |
| `neg__shape2_update_cell_sets_only.cpp` | negative | positive | 0.9302 | 0.9302 | FAIL | clean case scored 0.9302, required < 0.8 |
| `neg__shape3_query_local_init.cpp` | negative | positive | 0.8182 | 0.8182 | FAIL | add negatives and rebuild — no threshold tuning |
| `neg__shape4_request_reset_delegates.cpp` | negative | negative | 0.9560 | 0.0440 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | positive | 0.9397 | 0.9397 | FAIL | clean case scored 0.9397, required < 0.8 |
| `neg__to_millivolts.cpp` | negative | positive | 0.9373 | 0.9373 | FAIL | clean case scored 0.9373, required < 0.8 |
| `pos__shape5_update_cell_else_clears.cpp` | positive | positive | 0.9496 | 0.9496 | PASS |  |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 0.9503 | 0.9503 | PASS |  |
| `pos__shape7_poll_cell_reinit_before_evaluate.cpp` | positive | positive | 0.9568 | 0.9568 | PASS |  |

**Summary: 10/25 cases passed.**

## output-param-written-before-error-check

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | positive | 0.8917 | 0.8917 | FAIL | clean case scored 0.8917, required < 0.8 |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.6887 | 0.3113 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | positive | 0.8526 | 0.8526 | FAIL | clean case scored 0.8526, required < 0.8 |
| `neg__cellsensor_ctor.cpp` | negative | positive | 0.8716 | 0.8716 | FAIL | clean case scored 0.8716, required < 0.8 |
| `neg__fault_count.cpp` | negative | negative | 0.6986 | 0.3014 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.7240 | 0.2760 | PASS |  |
| `neg__get_cell_fault.cpp` | negative | positive | 0.7770 | 0.7770 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | positive | 0.8630 | 0.8630 | FAIL | clean case scored 0.8630, required < 0.8 |
| `neg__has_any_fault.cpp` | negative | negative | 0.8016 | 0.1984 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | positive | 0.5194 | 0.5194 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.6930 | 0.3070 | PASS |  |
| `neg__poll_all.cpp` | negative | positive | 0.7497 | 0.7497 | PASS |  |
| `neg__poll_cell.cpp` | negative | positive | 0.9017 | 0.9017 | FAIL | clean case scored 0.9017, required < 0.8 |
| `neg__read_cell_temp.cpp` | negative | positive | 0.8646 | 0.8646 | FAIL | clean case scored 0.8646, required < 0.8 |
| `neg__read_cell_voltage.cpp` | negative | positive | 0.8686 | 0.8686 | FAIL | clean case scored 0.8686, required < 0.8 |
| `neg__read_temp_raw.cpp` | negative | positive | 0.7736 | 0.7736 | PASS |  |
| `neg__read_voltage_raw.cpp` | negative | positive | 0.7713 | 0.7713 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.6106 | 0.3894 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.6413 | 0.3587 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | positive | 0.6906 | 0.6906 | PASS |  |
| `neg__to_millivolts.cpp` | negative | positive | 0.6234 | 0.6234 | PASS |  |
| `neg__update_cell.cpp` | negative | positive | 0.9026 | 0.9026 | FAIL | clean case scored 0.9026, required < 0.8 |
| `pos__get_last_voltage_write_before_check.cpp` | positive | positive | 0.8183 | 0.8183 | FAIL | violation case scored 0.8183, required > 0.85 |
| `pos__read_cell_voltage_sentinel_clobbered.cpp` | positive | positive | 0.8858 | 0.8858 | PASS |  |
| `pos__read_temp_raw_init_at_top.cpp` | positive | positive | 0.8078 | 0.8078 | FAIL | violation case scored 0.8078, required > 0.85 |
| `pos__read_voltage_raw_init_at_top.cpp` | positive | positive | 0.8369 | 0.8369 | FAIL | violation case scored 0.8369, required > 0.85 |
| `pos__to_deci_celsius_write_before_check.cpp` | positive | positive | 0.6467 | 0.6467 | FAIL | violation case scored 0.6467, required > 0.85 |
| `pos__to_millivolts_write_before_check.cpp` | positive | positive | 0.5541 | 0.5541 | FAIL | violation case scored 0.5541, required > 0.85 |

**Summary: 15/28 cases passed.**

## platform-dependent-integer-types

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | negative | 0.9605 | 0.0395 | PASS |  |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.9606 | 0.0394 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9581 | 0.0419 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | negative | 0.9611 | 0.0389 | PASS |  |
| `neg__fault_count.cpp` | negative | negative | 0.9607 | 0.0393 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.9615 | 0.0385 | PASS |  |
| `neg__get_cell_fault.cpp` | negative | negative | 0.9587 | 0.0413 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | negative | 0.9582 | 0.0418 | PASS |  |
| `neg__has_any_fault.cpp` | negative | negative | 0.9609 | 0.0391 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.9579 | 0.0421 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9592 | 0.0408 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9596 | 0.0404 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.9579 | 0.0421 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | negative | 0.9584 | 0.0416 | PASS |  |
| `neg__read_cell_voltage.cpp` | negative | negative | 0.9590 | 0.0410 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | negative | 0.9583 | 0.0417 | PASS |  |
| `neg__read_voltage_raw.cpp` | negative | negative | 0.9588 | 0.0412 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.9558 | 0.0442 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.9611 | 0.0389 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | negative | 0.9601 | 0.0399 | PASS |  |
| `neg__to_millivolts.cpp` | negative | negative | 0.9605 | 0.0395 | PASS |  |
| `neg__update_cell.cpp` | negative | negative | 0.9577 | 0.0423 | PASS |  |
| `pos__fault_count_bare_int.cpp` | positive | negative | 0.9615 | 0.0385 | FAIL | violation case scored 0.0385, required > 0.85 |
| `pos__get_last_voltage_bare_int.cpp` | positive | negative | 0.9588 | 0.0412 | FAIL | violation case scored 0.0412, required > 0.85 |
| `pos__poll_all_bare_int.cpp` | positive | negative | 0.9603 | 0.0397 | FAIL | violation case scored 0.0397, required > 0.85 |
| `pos__read_voltage_raw_bare_int.cpp` | positive | negative | 0.9588 | 0.0412 | FAIL | violation case scored 0.0412, required > 0.85 |
| `pos__to_millivolts_bare_int.cpp` | positive | negative | 0.9605 | 0.0395 | FAIL | violation case scored 0.0395, required > 0.85 |
| `pos__update_cell_bare_int.cpp` | positive | negative | 0.9579 | 0.0421 | FAIL | violation case scored 0.0421, required > 0.85 |

**Summary: 22/28 cases passed.**

## raw-threshold-comparison-in-decision-logic

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__inv_batterysupervisor_ctor.cpp` | negative | negative | 0.9563 | 0.0437 | PASS |  |
| `neg__inv_cellmonitor_ctor.cpp` | negative | negative | 0.9560 | 0.0440 | PASS |  |
| `neg__inv_cellsensor_configure.cpp` | negative | negative | 0.9564 | 0.0436 | PASS |  |
| `neg__inv_cellsensor_ctor.cpp` | negative | negative | 0.8642 | 0.1358 | PASS |  |
| `neg__inv_fault_count.cpp` | negative | positive | 0.5194 | 0.5194 | PASS |  |
| `neg__inv_faultmanager_ctor.cpp` | negative | positive | 0.8743 | 0.8743 | FAIL | clean case scored 0.8743, required < 0.8 |
| `neg__inv_get_cell_fault.cpp` | negative | negative | 0.9559 | 0.0441 | PASS |  |
| `neg__inv_get_last_voltage.cpp` | negative | negative | 0.9593 | 0.0407 | PASS |  |
| `neg__inv_has_any_fault.cpp` | negative | positive | 0.9186 | 0.9186 | FAIL | clean case scored 0.9186, required < 0.8 |
| `neg__inv_is_contactor_closed.cpp` | negative | positive | 0.9586 | 0.9586 | FAIL | clean case scored 0.9586, required < 0.8 |
| `neg__inv_is_ready.cpp` | negative | negative | 0.9559 | 0.0441 | PASS |  |
| `neg__inv_poll_all.cpp` | negative | negative | 0.9569 | 0.0431 | PASS |  |
| `neg__inv_poll_cell_spec_correct.cpp` | negative | negative | 0.9596 | 0.0404 | PASS |  |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.9588 | 0.0412 | PASS |  |
| `neg__inv_read_cell_voltage.cpp` | negative | negative | 0.9581 | 0.0419 | PASS |  |
| `neg__inv_read_temp_raw.cpp` | negative | negative | 0.9558 | 0.0442 | PASS |  |
| `neg__inv_request_reset.cpp` | negative | positive | 0.9560 | 0.9560 | FAIL | clean case scored 0.9560, required < 0.8 |
| `neg__inv_reset_faults.cpp` | negative | positive | 0.8626 | 0.8626 | FAIL | clean case scored 0.8626, required < 0.8 |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.9590 | 0.0410 | PASS |  |
| `neg__shape1_decision_on_engineering_units.cpp` | negative | negative | 0.9600 | 0.0400 | PASS |  |
| `neg__shape2_conversion_range_check.cpp` | negative | negative | 0.9588 | 0.0412 | PASS |  |
| `neg__shape3_hal_bounds_check.cpp` | negative | negative | 0.9552 | 0.0448 | PASS |  |
| `pos__shape4_raw_vs_bare_literal.cpp` | positive | negative | 0.9585 | 0.0415 | FAIL | violation case scored 0.0415, required > 0.85 |
| `pos__shape5_raw_vs_counts_constant.cpp` | positive | negative | 0.9577 | 0.0423 | FAIL | violation case scored 0.0423, required > 0.85 |
| `pos__shape6_poll_cell_raw_shortcut.cpp` | positive | negative | 0.9570 | 0.0430 | FAIL | violation case scored 0.0430, required > 0.85 |

**Summary: 17/25 cases passed.**

## state-mutation-in-diagnostic-query

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__inv_batterysupervisor_ctor.cpp` | negative | negative | 0.9119 | 0.0881 | PASS |  |
| `neg__inv_cellmonitor_ctor.cpp` | negative | negative | 0.9275 | 0.0725 | PASS |  |
| `neg__inv_cellsensor_ctor.cpp` | negative | negative | 0.8806 | 0.1194 | PASS |  |
| `neg__inv_faultmanager_ctor.cpp` | negative | negative | 0.9355 | 0.0645 | PASS |  |
| `neg__inv_poll_all.cpp` | negative | negative | 0.8350 | 0.1650 | PASS |  |
| `neg__inv_poll_cell.cpp` | negative | positive | 0.6172 | 0.6172 | PASS |  |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.7194 | 0.2806 | PASS |  |
| `neg__inv_read_cell_voltage.cpp` | negative | positive | 0.7335 | 0.7335 | PASS |  |
| `neg__inv_read_temp_raw.cpp` | negative | positive | 0.9229 | 0.9229 | FAIL | clean case scored 0.9229, required < 0.8 |
| `neg__inv_read_voltage_raw.cpp` | negative | positive | 0.9222 | 0.9222 | FAIL | clean case scored 0.9222, required < 0.8 |
| `neg__inv_request_reset.cpp` | negative | negative | 0.9447 | 0.0553 | PASS |  |
| `neg__inv_reset_faults.cpp` | negative | negative | 0.9451 | 0.0549 | PASS |  |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.9011 | 0.0989 | PASS |  |
| `neg__inv_to_millivolts.cpp` | negative | negative | 0.8454 | 0.1546 | PASS |  |
| `neg__inv_update_cell.cpp` | negative | positive | 0.7307 | 0.7307 | PASS |  |
| `neg__shape1_has_any_fault_loop.cpp` | negative | negative | 0.6959 | 0.3041 | PASS |  |
| `neg__shape2_fault_count_local_accumulator.cpp` | negative | negative | 0.9302 | 0.0698 | PASS |  |
| `neg__shape3_is_ready_indexes_member.cpp` | negative | positive | 0.9325 | 0.9325 | FAIL | clean case scored 0.9325, required < 0.8 |
| `neg__shape4_is_contactor_closed_delegates.cpp` | negative | positive | 0.9338 | 0.9338 | FAIL | clean case scored 0.9338, required < 0.8 |
| `neg__shape5_configure_command_mutates.cpp` | negative | negative | 0.9224 | 0.0776 | PASS |  |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 0.8921 | 0.8921 | PASS |  |
| `pos__shape7_get_last_voltage_lazy_refresh.cpp` | positive | positive | 0.9063 | 0.9063 | PASS |  |

**Summary: 18/22 cases passed.**

---

**Overall result: FAIL**
