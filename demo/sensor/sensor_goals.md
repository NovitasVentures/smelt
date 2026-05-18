# Embedded Sensor Pipeline — Test Goals

All tests use GTest. Test names follow: `TEST(ModuleName, Method_Scenario_ExpectedOutcome)`.

---

## SensorDriver (HAL layer)

### `read_raw`

- A sensor configured as ready with a known raw value returns `ErrorCode::OK` and writes
  that exact value to the output parameter
- A sensor not yet configured as ready returns `ErrorCode::SENSOR_NOT_READY` and leaves
  the output parameter unmodified
- An out-of-range `SensorId` cast to a valid enum value returns `ErrorCode::INVALID_ARGUMENT`
  and leaves the output parameter unmodified
- Calling `read_raw` twice in sequence for the same ready sensor returns `ErrorCode::OK`
  both times with the same value
- `read_raw` for a not-ready sensor does not write anything: output parameter retains its
  sentinel value from before the call

### `is_ready`

- Returns `false` before `configure` is called for a sensor
- Returns `true` after `configure` is called with `ready = true`
- Returns `false` after `configure` is called with `ready = false`

---

## SensorProcessor (Processing layer)

### `calibrate`

- With default coefficients (`scale=0.01, offset=0.0`), a raw value of 1000 produces
  a calibrated output of `10.0f` (within `1e-4f` tolerance)
- With custom coefficients set via `set_calibration`, the calibrated output reflects
  those coefficients
- An out-of-range `SensorId` returns `ErrorCode::INVALID_ARGUMENT` and leaves
  `out_calibrated` unmodified
- A zero raw value produces a calibrated output of `offset` only

### `filter`

- The mean of `{1.0f, 2.0f, 3.0f}` (count=3) is `2.0f` (within `1e-5f` tolerance)
- A null `samples` pointer returns `ErrorCode::INVALID_ARGUMENT` and leaves
  `out_filtered` unmodified
- A count of zero returns `ErrorCode::INVALID_ARGUMENT` and leaves `out_filtered`
  unmodified
- A single-element array returns `ErrorCode::OK` with output equal to that element

### `acquire`

- For a sensor configured as ready with raw value 500, `acquire` returns `ErrorCode::OK`
  and writes a calibrated value consistent with the default coefficients (`500 * 0.01 = 5.0f`)
- When the sensor is not ready, `acquire` returns `ErrorCode::SENSOR_NOT_READY` and
  leaves `out_value` unmodified
- When `read_raw` returns `SENSOR_FAULT`, `acquire` returns `ErrorCode::SENSOR_FAULT`
  and leaves `out_value` unmodified
- Custom calibration coefficients are reflected in the output of `acquire`
- The output parameter retains its original sentinel value on every error path

---

## SensorDispatcher (Application layer)

### `sample_and_dispatch`

- When all three acquire calls succeed and the filtered mean is below `threshold`,
  returns `ErrorCode::OK`
- When all three acquire calls succeed and the filtered mean strictly exceeds `threshold`,
  returns `ErrorCode::THRESHOLD_EXCEEDED`
- When `threshold` equals the filtered mean (not strictly greater), returns `ErrorCode::OK`
- When the first `acquire` call fails, returns that error code immediately without
  attempting further acquires
- When the second `acquire` call fails (first succeeds), returns that error code
- When all acquires succeed but `filter` fails, returns `ErrorCode::SENSOR_FAULT`
- After a successful `sample_and_dispatch` that returns `THRESHOLD_EXCEEDED`, the cached
  value is accessible via `get_last_reading`
- After a failed `sample_and_dispatch` (acquire error), `get_last_reading` for that
  sensor still returns `ErrorCode::SENSOR_NOT_READY` (cache not updated)

### `get_last_reading`

- Before any successful `sample_and_dispatch`, returns `ErrorCode::SENSOR_NOT_READY`
  and leaves `out_value` unmodified
- After a successful `sample_and_dispatch`, returns `ErrorCode::OK` and writes the
  filtered value
- The cached value reflects the most recent successful `sample_and_dispatch`
- An out-of-range `SensorId` returns `ErrorCode::INVALID_ARGUMENT` and leaves
  `out_value` unmodified
- `get_last_reading` output parameter retains its sentinel value on every error path

### Output parameter discipline (cross-method)

- `read_raw`: sentinel survives a `SENSOR_NOT_READY` return
- `read_raw`: sentinel survives an `INVALID_ARGUMENT` return
- `calibrate`: sentinel survives an `INVALID_ARGUMENT` return
- `filter`: sentinel survives a null-samples `INVALID_ARGUMENT` return
- `filter`: sentinel survives a zero-count `INVALID_ARGUMENT` return
- `acquire`: sentinel survives every non-OK return from `acquire`
- `get_last_reading`: sentinel survives a `SENSOR_NOT_READY` return
- `get_last_reading`: sentinel survives an `INVALID_ARGUMENT` return

Each "sentinel survives" test sets the output parameter to a known sentinel value
(e.g., `0xDEAD` cast to the appropriate type), calls the function expecting an error
return, then asserts the output parameter still holds the sentinel.
