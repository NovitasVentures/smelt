# BMS Cell Monitoring and Fault Management — Test Goals

All tests use GTest. Test names follow: `TEST(ModuleName, Method_Scenario_ExpectedOutcome)`.
One `TEST()` per logical behavior — each test sets up state, performs the action, and
asserts a single observable outcome.

---

## CellSensor (HAL layer)

### `read_voltage_raw`

- A cell configured as ready with raw voltage 2867 returns `ErrorCode::OK` and writes
  exactly 2867 to the output parameter
- A cell not yet configured as ready returns `ErrorCode::SENSOR_NOT_READY` and leaves
  the output parameter unmodified
- An out-of-range cell index (`CELL_COUNT` or greater) returns
  `ErrorCode::INVALID_ARGUMENT` and leaves the output parameter unmodified
- Calling `read_voltage_raw` twice in sequence for the same ready cell returns
  `ErrorCode::OK` both times with the same value

### `read_temp_raw`

- A cell configured as ready with raw temperature 2048 returns `ErrorCode::OK` and
  writes exactly 2048 to the output parameter
- A cell not configured as ready returns `ErrorCode::SENSOR_NOT_READY` and leaves the
  output parameter unmodified
- An out-of-range cell index returns `ErrorCode::INVALID_ARGUMENT` and leaves the
  output parameter unmodified

### `is_ready`

- Returns `false` before `configure` is called for a cell
- Returns `true` after `configure` is called with `ready = true`
- Returns `false` after `configure` is called with `ready = false`
- Returns `false` for an out-of-range cell index

---

## CellMonitor (Monitoring layer)

### `to_millivolts`

- Raw count 2048 converts to exactly 2500 mV
- Raw count 0 converts to exactly 0 mV
- Raw count 4095 converts to exactly 5000 mV
- Raw count −1 returns `ErrorCode::HARDWARE_FAULT` and leaves `out_mv` unmodified
- Raw count 4096 returns `ErrorCode::HARDWARE_FAULT` and leaves `out_mv` unmodified

### `to_deci_celsius`

- Raw count 2048 converts to exactly 425 deci-degrees (42.5 °C)
- Raw count 0 converts to exactly −400 deci-degrees (−40.0 °C)
- Raw count 4095 converts to exactly 1250 deci-degrees (125.0 °C)
- Raw count 4096 returns `ErrorCode::HARDWARE_FAULT` and leaves `out_dc` unmodified

### `read_cell_voltage`

- For a cell configured ready with raw voltage 2867, returns `ErrorCode::OK` and
  writes 3500 mV
- For a cell not configured ready, returns `ErrorCode::SENSOR_NOT_READY` and leaves
  `out_mv` unmodified
- For an out-of-range cell index, returns `ErrorCode::INVALID_ARGUMENT` and leaves
  `out_mv` unmodified

### `read_cell_temp`

- For a cell configured ready with raw temperature 2048, returns `ErrorCode::OK` and
  writes 425 deci-degrees
- For a cell not configured ready, returns `ErrorCode::SENSOR_NOT_READY` and leaves
  `out_dc` unmodified

---

## FaultManager (Monitoring layer)

All voltage/temperature inputs below are engineering-unit values passed directly to
`update_cell`.

### `update_cell` / `get_cell_fault`

- After `update_cell(0, 3500, 425)` from a clean state, `get_cell_fault(0)` returns
  `FaultType::NONE`
- After `update_cell(0, 4395, 425)`, `get_cell_fault(0)` returns
  `FaultType::OVER_VOLTAGE`
- After `update_cell(0, 2686, 425)`, `get_cell_fault(0)` returns
  `FaultType::UNDER_VOLTAGE`
- After `update_cell(0, 3500, 728)`, `get_cell_fault(0)` returns
  `FaultType::OVER_TEMP`
- After `update_cell(0, 4395, 728)` (overvoltage and overtemperature in the same
  call), `get_cell_fault(0)` returns `FaultType::OVER_VOLTAGE` (precedence)
- After `update_cell(0, 4200, 425)` (exactly at the overvoltage threshold),
  `get_cell_fault(0)` returns `FaultType::NONE` (strictly-greater comparison)
- After `update_cell(0, 2800, 425)` (exactly at the undervoltage threshold),
  `get_cell_fault(0)` returns `FaultType::NONE` (strictly-less comparison)
- After `update_cell(0, 3500, 600)` (exactly at the overtemperature threshold),
  `get_cell_fault(0)` returns `FaultType::NONE`
- `update_cell` with an out-of-range cell index returns `ErrorCode::INVALID_ARGUMENT`
- `update_cell` with an in-range cell returns `ErrorCode::OK` whether or not a fault
  was recorded
- `get_cell_fault` with an out-of-range cell index returns `FaultType::NONE`

### `has_any_fault`

- Returns `false` from a clean state
- Returns `true` after `update_cell(2, 4395, 425)`

### `fault_count`

- Returns 0 from a clean state
- Returns 2 after faulting two different cells (`update_cell(1, 4395, 425)` and
  `update_cell(5, 2686, 425)`)

### `reset_faults`

- After `update_cell(0, 4395, 425)` followed by `reset_faults()`, `get_cell_fault(0)`
  returns `FaultType::NONE`
- After faulting two cells followed by `reset_faults()`, `fault_count()` returns 0
- After a fault and a `reset_faults()`, `has_any_fault()` returns `false`

---

## BatterySupervisor (Supervision layer)

### `poll_cell`

- For a cell configured ready with raw voltage 2867 and raw temperature 2048,
  `poll_cell` returns `ErrorCode::OK`
- After that successful poll, `get_last_voltage` for the cell returns
  `ErrorCode::OK` and writes 3500 mV
- For a cell not configured ready, `poll_cell` returns `ErrorCode::SENSOR_NOT_READY`
- After a failed poll (cell not ready), `get_last_voltage` for that cell still
  returns `ErrorCode::SENSOR_NOT_READY` (cache not updated)
- `poll_cell` with an out-of-range cell index returns `ErrorCode::INVALID_ARGUMENT`
- After polling a cell whose raw voltage is 3600 (4395 mV, overvoltage),
  `is_contactor_closed()` returns `false`
- After polling a cell whose raw voltage is 2200 (2686 mV, undervoltage),
  `has_any_fault()` on the fault manager returns `true`
- After polling a cell with nominal raw values (2867 voltage, 2048 temperature),
  `is_contactor_closed()` returns `true`

### `poll_all`

- With all eight cells configured ready at nominal raw values, `poll_all` returns
  `ErrorCode::OK`
- With cell 3 not configured ready and all others ready, `poll_all` returns
  `ErrorCode::SENSOR_NOT_READY`
- After that failed `poll_all`, `get_last_voltage(4, ...)` returns
  `ErrorCode::SENSOR_NOT_READY` (polling stopped at the first error; cell 4 was
  never polled)

### `get_last_voltage`

- Before any successful poll, returns `ErrorCode::SENSOR_NOT_READY` and leaves
  `out_mv` unmodified
- With an out-of-range cell index, returns `ErrorCode::INVALID_ARGUMENT` and leaves
  `out_mv` unmodified
- After two successful polls with different injected raw values, returns the value
  from the most recent poll

### `is_contactor_closed` / `request_reset`

- `is_contactor_closed()` returns `true` before any poll
- After a poll that records an overvoltage fault, followed by `request_reset()`,
  `is_contactor_closed()` returns `true`

---

## Output parameter discipline (cross-method)

Each "sentinel survives" test sets the output parameter to a known sentinel value
(e.g., `0x7FFFDEAD` for `int32_t`), calls the function expecting an error return,
then asserts the output parameter still holds the sentinel.

- `read_voltage_raw`: sentinel survives a `SENSOR_NOT_READY` return
- `read_voltage_raw`: sentinel survives an `INVALID_ARGUMENT` return
- `read_temp_raw`: sentinel survives a `SENSOR_NOT_READY` return
- `to_millivolts`: sentinel survives a `HARDWARE_FAULT` return
- `to_deci_celsius`: sentinel survives a `HARDWARE_FAULT` return
- `read_cell_voltage`: sentinel survives every non-OK return
- `read_cell_temp`: sentinel survives every non-OK return
- `get_last_voltage`: sentinel survives a `SENSOR_NOT_READY` return
- `get_last_voltage`: sentinel survives an `INVALID_ARGUMENT` return
