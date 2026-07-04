# Demo 8 BMS — Specialist Verification Report

Models directory: `/home/aoaustin/projects/smelt/demo/bms/specialists`

Acceptance rule: violation cases must score above 0.85; clean cases must score below 0.8. A clean case scoring in [0.8, 0.85) is a FAIL — add negatives and rebuild, no threshold tuning.

## fault-cleared-outside-reset

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | negative | 0.9752 | 0.0248 | PASS |  |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.9702 | 0.0298 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9676 | 0.0324 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | negative | 0.9762 | 0.0238 | PASS |  |
| `neg__fault_count.cpp` | negative | negative | 0.9770 | 0.0230 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.9773 | 0.0227 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | negative | 0.9767 | 0.0233 | PASS |  |
| `neg__has_any_fault.cpp` | negative | negative | 0.9764 | 0.0236 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.9752 | 0.0248 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9772 | 0.0228 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9734 | 0.0266 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.9748 | 0.0252 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | negative | 0.9755 | 0.0245 | PASS |  |
| `neg__read_cell_voltage.cpp` | negative | negative | 0.9758 | 0.0242 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | negative | 0.9763 | 0.0237 | PASS |  |
| `neg__read_voltage_raw.cpp` | negative | negative | 0.9764 | 0.0236 | PASS |  |
| `neg__shape1_reset_faults_loop.cpp` | negative | negative | 0.9770 | 0.0230 | PASS |  |
| `neg__shape2_update_cell_sets_only.cpp` | negative | negative | 0.9712 | 0.0288 | PASS |  |
| `neg__shape3_query_local_init.cpp` | negative | positive | 0.7534 | 0.7534 | PASS |  |
| `neg__shape4_request_reset_delegates.cpp` | negative | negative | 0.9460 | 0.0540 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | negative | 0.9739 | 0.0261 | PASS |  |
| `neg__to_millivolts.cpp` | negative | negative | 0.9762 | 0.0238 | PASS |  |
| `pos__shape5_update_cell_else_clears.cpp` | positive | negative | 0.9398 | 0.0602 | FAIL | violation case scored 0.0602, required > 0.85 |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 0.9751 | 0.9751 | PASS |  |
| `pos__shape7_poll_cell_reinit_before_evaluate.cpp` | positive | negative | 0.9748 | 0.0252 | FAIL | violation case scored 0.0252, required > 0.85 |

**Summary: 23/25 cases passed.**

## output-param-written-before-error-check

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | negative | 0.9681 | 0.0319 | PASS |  |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.9677 | 0.0323 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9651 | 0.0349 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | negative | 0.9687 | 0.0313 | PASS |  |
| `neg__fault_count.cpp` | negative | negative | 0.9685 | 0.0315 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.9691 | 0.0309 | PASS |  |
| `neg__get_cell_fault.cpp` | negative | negative | 0.9688 | 0.0312 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | positive | 0.9224 | 0.9224 | FAIL | clean case scored 0.9224, required < 0.8 |
| `neg__has_any_fault.cpp` | negative | negative | 0.9691 | 0.0309 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.9684 | 0.0316 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9684 | 0.0316 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9682 | 0.0318 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.9638 | 0.0362 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | positive | 0.9180 | 0.9180 | FAIL | clean case scored 0.9180, required < 0.8 |
| `neg__read_cell_voltage.cpp` | negative | positive | 0.6535 | 0.6535 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | positive | 0.8832 | 0.8832 | FAIL | clean case scored 0.8832, required < 0.8 |
| `neg__read_voltage_raw.cpp` | negative | positive | 0.5284 | 0.5284 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.9688 | 0.0312 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.9690 | 0.0310 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | positive | 0.9594 | 0.9594 | FAIL | clean case scored 0.9594, required < 0.8 |
| `neg__to_millivolts.cpp` | negative | positive | 0.9489 | 0.9489 | FAIL | clean case scored 0.9489, required < 0.8 |
| `neg__update_cell.cpp` | negative | negative | 0.9604 | 0.0396 | PASS |  |
| `pos__get_last_voltage_write_before_check.cpp` | positive | positive | 0.9447 | 0.9447 | PASS |  |
| `pos__read_cell_voltage_sentinel_clobbered.cpp` | positive | positive | 0.9646 | 0.9646 | PASS |  |
| `pos__read_temp_raw_init_at_top.cpp` | positive | positive | 0.9643 | 0.9643 | PASS |  |
| `pos__read_voltage_raw_init_at_top.cpp` | positive | positive | 0.9640 | 0.9640 | PASS |  |
| `pos__to_deci_celsius_write_before_check.cpp` | positive | positive | 0.9625 | 0.9625 | PASS |  |
| `pos__to_millivolts_write_before_check.cpp` | positive | positive | 0.9633 | 0.9633 | PASS |  |

**Summary: 23/28 cases passed.**

## platform-dependent-integer-types

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__batterysupervisor_ctor.cpp` | negative | negative | 0.8857 | 0.1143 | PASS |  |
| `neg__cellmonitor_ctor.cpp` | negative | negative | 0.7270 | 0.2730 | PASS |  |
| `neg__cellsensor_configure.cpp` | negative | negative | 0.9148 | 0.0852 | PASS |  |
| `neg__cellsensor_ctor.cpp` | negative | negative | 0.9190 | 0.0810 | PASS |  |
| `neg__fault_count.cpp` | negative | negative | 0.9213 | 0.0787 | PASS |  |
| `neg__faultmanager_ctor.cpp` | negative | negative | 0.9191 | 0.0809 | PASS |  |
| `neg__get_cell_fault.cpp` | negative | negative | 0.9177 | 0.0823 | PASS |  |
| `neg__get_last_voltage.cpp` | negative | negative | 0.9168 | 0.0832 | PASS |  |
| `neg__has_any_fault.cpp` | negative | negative | 0.9177 | 0.0823 | PASS |  |
| `neg__is_contactor_closed.cpp` | negative | negative | 0.8703 | 0.1297 | PASS |  |
| `neg__is_ready.cpp` | negative | negative | 0.9189 | 0.0811 | PASS |  |
| `neg__poll_all.cpp` | negative | negative | 0.9151 | 0.0849 | PASS |  |
| `neg__poll_cell.cpp` | negative | negative | 0.9123 | 0.0877 | PASS |  |
| `neg__read_cell_temp.cpp` | negative | negative | 0.9141 | 0.0859 | PASS |  |
| `neg__read_cell_voltage.cpp` | negative | negative | 0.9114 | 0.0886 | PASS |  |
| `neg__read_temp_raw.cpp` | negative | negative | 0.9161 | 0.0839 | PASS |  |
| `neg__read_voltage_raw.cpp` | negative | negative | 0.9137 | 0.0863 | PASS |  |
| `neg__request_reset.cpp` | negative | negative | 0.8616 | 0.1384 | PASS |  |
| `neg__reset_faults.cpp` | negative | negative | 0.9193 | 0.0807 | PASS |  |
| `neg__to_deci_celsius.cpp` | negative | negative | 0.8871 | 0.1129 | PASS |  |
| `neg__to_millivolts.cpp` | negative | negative | 0.8916 | 0.1084 | PASS |  |
| `neg__update_cell.cpp` | negative | negative | 0.9093 | 0.0907 | PASS |  |
| `pos__fault_count_bare_int.cpp` | positive | positive | 0.9106 | 0.9106 | PASS |  |
| `pos__get_last_voltage_bare_int.cpp` | positive | positive | 0.9108 | 0.9108 | PASS |  |
| `pos__poll_all_bare_int.cpp` | positive | positive | 0.9041 | 0.9041 | PASS |  |
| `pos__read_voltage_raw_bare_int.cpp` | positive | positive | 0.9108 | 0.9108 | PASS |  |
| `pos__to_millivolts_bare_int.cpp` | positive | positive | 0.9054 | 0.9054 | PASS |  |
| `pos__update_cell_bare_int.cpp` | positive | positive | 0.9109 | 0.9109 | PASS |  |

**Summary: 28/28 cases passed.**

## raw-threshold-comparison-in-decision-logic

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__inv_batterysupervisor_ctor.cpp` | negative | negative | 0.9455 | 0.0545 | PASS |  |
| `neg__inv_cellmonitor_ctor.cpp` | negative | negative | 0.9077 | 0.0923 | PASS |  |
| `neg__inv_cellsensor_configure.cpp` | negative | positive | 0.7081 | 0.7081 | PASS |  |
| `neg__inv_cellsensor_ctor.cpp` | negative | negative | 0.9484 | 0.0516 | PASS |  |
| `neg__inv_fault_count.cpp` | negative | negative | 0.9492 | 0.0508 | PASS |  |
| `neg__inv_faultmanager_ctor.cpp` | negative | negative | 0.9491 | 0.0509 | PASS |  |
| `neg__inv_get_cell_fault.cpp` | negative | negative | 0.9498 | 0.0502 | PASS |  |
| `neg__inv_get_last_voltage.cpp` | negative | negative | 0.9499 | 0.0501 | PASS |  |
| `neg__inv_has_any_fault.cpp` | negative | negative | 0.9494 | 0.0506 | PASS |  |
| `neg__inv_is_contactor_closed.cpp` | negative | negative | 0.9349 | 0.0651 | PASS |  |
| `neg__inv_is_ready.cpp` | negative | negative | 0.9494 | 0.0506 | PASS |  |
| `neg__inv_poll_all.cpp` | negative | negative | 0.9489 | 0.0511 | PASS |  |
| `neg__inv_poll_cell_spec_correct.cpp` | negative | negative | 0.9494 | 0.0506 | PASS |  |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.9489 | 0.0511 | PASS |  |
| `neg__inv_read_cell_voltage.cpp` | negative | negative | 0.9490 | 0.0510 | PASS |  |
| `neg__inv_read_temp_raw.cpp` | negative | negative | 0.9493 | 0.0507 | PASS |  |
| `neg__inv_request_reset.cpp` | negative | negative | 0.9477 | 0.0523 | PASS |  |
| `neg__inv_reset_faults.cpp` | negative | negative | 0.9492 | 0.0508 | PASS |  |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.9446 | 0.0554 | PASS |  |
| `neg__shape1_decision_on_engineering_units.cpp` | negative | negative | 0.9491 | 0.0509 | PASS |  |
| `neg__shape2_conversion_range_check.cpp` | negative | negative | 0.9449 | 0.0551 | PASS |  |
| `neg__shape3_hal_bounds_check.cpp` | negative | negative | 0.9492 | 0.0508 | PASS |  |
| `pos__shape4_raw_vs_bare_literal.cpp` | positive | positive | 0.9573 | 0.9573 | PASS |  |
| `pos__shape5_raw_vs_counts_constant.cpp` | positive | positive | 0.9561 | 0.9561 | PASS |  |
| `pos__shape6_poll_cell_raw_shortcut.cpp` | positive | positive | 0.9577 | 0.9577 | PASS |  |

**Summary: 25/25 cases passed.**

## state-mutation-in-diagnostic-query

| Case | Expected | Label | Confidence | Score | Verdict | Note |
|---|---|---|---|---|---|---|
| `neg__inv_batterysupervisor_ctor.cpp` | negative | positive | 0.5124 | 0.5124 | PASS |  |
| `neg__inv_cellmonitor_ctor.cpp` | negative | negative | 0.9212 | 0.0788 | PASS |  |
| `neg__inv_cellsensor_ctor.cpp` | negative | negative | 0.9128 | 0.0872 | PASS |  |
| `neg__inv_faultmanager_ctor.cpp` | negative | negative | 0.9289 | 0.0711 | PASS |  |
| `neg__inv_poll_all.cpp` | negative | negative | 0.9244 | 0.0756 | PASS |  |
| `neg__inv_poll_cell.cpp` | negative | negative | 0.9174 | 0.0826 | PASS |  |
| `neg__inv_read_cell_temp.cpp` | negative | negative | 0.9165 | 0.0835 | PASS |  |
| `neg__inv_read_cell_voltage.cpp` | negative | negative | 0.7616 | 0.2384 | PASS |  |
| `neg__inv_read_temp_raw.cpp` | negative | positive | 0.5536 | 0.5536 | PASS |  |
| `neg__inv_read_voltage_raw.cpp` | negative | negative | 0.5547 | 0.4453 | PASS |  |
| `neg__inv_request_reset.cpp` | negative | negative | 0.9260 | 0.0740 | PASS |  |
| `neg__inv_reset_faults.cpp` | negative | negative | 0.9298 | 0.0702 | PASS |  |
| `neg__inv_to_deci_celsius.cpp` | negative | negative | 0.9133 | 0.0867 | PASS |  |
| `neg__inv_to_millivolts.cpp` | negative | negative | 0.8832 | 0.1168 | PASS |  |
| `neg__inv_update_cell.cpp` | negative | negative | 0.8567 | 0.1433 | PASS |  |
| `neg__shape1_has_any_fault_loop.cpp` | negative | negative | 0.9282 | 0.0718 | PASS |  |
| `neg__shape2_fault_count_local_accumulator.cpp` | negative | negative | 0.9169 | 0.0831 | PASS |  |
| `neg__shape3_is_ready_indexes_member.cpp` | negative | negative | 0.9210 | 0.0790 | PASS |  |
| `neg__shape4_is_contactor_closed_delegates.cpp` | negative | negative | 0.9202 | 0.0798 | PASS |  |
| `neg__shape5_configure_command_mutates.cpp` | negative | negative | 0.8634 | 0.1366 | PASS |  |
| `pos__shape6_get_cell_fault_read_clears.cpp` | positive | positive | 0.9218 | 0.9218 | PASS |  |
| `pos__shape7_get_last_voltage_lazy_refresh.cpp` | positive | positive | 0.8785 | 0.8785 | PASS |  |

**Summary: 22/22 cases passed.**

---

**Overall result: FAIL**
