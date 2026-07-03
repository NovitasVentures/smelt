# BMS Cell Monitoring and Fault Management — Implementation Spec

Implement a three-layer C++14 library: `hal/`, `monitoring/`, and `supervision/`.
Each layer lives in its own directory. All headers use `#pragma once`. All integers
use `<cstdint>` fixed-width types. No exceptions — all errors communicated via
`ErrorCode`. All member function definitions live in `.cpp` files; headers contain
declarations only.

---

## Shared Type: `ErrorCode`

Defined in `common/error_code.h`. All layers include this header.

```cpp
#pragma once
#include <cstdint>

enum class ErrorCode : uint8_t {
    OK               = 0,
    INVALID_ARGUMENT = 1,
    SENSOR_NOT_READY = 2,
    HARDWARE_FAULT   = 3,
};
```

---

## Shared Types and Constants: `common/bms_types.h`

```cpp
#pragma once
#include <cstdint>

enum class FaultType : uint8_t {
    NONE          = 0,
    OVER_VOLTAGE  = 1,
    UNDER_VOLTAGE = 2,
    OVER_TEMP     = 3,
};

static constexpr uint8_t CELL_COUNT       = 8U;
static constexpr int32_t ADC_MAX_COUNTS   = 4095;   // 12-bit ADC

// Safety thresholds, engineering units.
static constexpr int32_t OVER_VOLTAGE_MV  = 4200;   // millivolts
static constexpr int32_t UNDER_VOLTAGE_MV = 2800;   // millivolts
static constexpr int32_t OVER_TEMP_DC     = 600;    // deci-degrees-Celsius (60.0 C)
```

---

## HAL Layer (`hal/`)

### `hal/cell_sensor.h` and `hal/cell_sensor.cpp`

`CellSensor` is the hardware abstraction for raw ADC reads. It maintains an internal
state table for each of the eight cells: a raw voltage count, a raw temperature
count, and a ready flag. In the real system this would talk to a cell-monitoring
ASIC over isoSPI; in this implementation it uses a configurable internal table that
tests can inject values into.

#### Constructor

```cpp
CellSensor()
```

Initializes all cell slots to not-ready with raw counts 0.

#### `CellSensor::configure(uint8_t cell, int32_t raw_voltage, int32_t raw_temp, bool ready) -> void`

Sets the simulated raw voltage count, raw temperature count, and ready state for a
given cell. Used by tests to inject known values. Not part of the operational
interface.

- Does nothing if `cell` is out of range (`cell >= CELL_COUNT`).

#### `CellSensor::read_voltage_raw(uint8_t cell, int32_t& out_counts) -> ErrorCode`

Reads the raw voltage ADC count for the given cell.

- Returns `ErrorCode::INVALID_ARGUMENT` if `cell` is out of range. Does not modify
  `out_counts`.
- Returns `ErrorCode::SENSOR_NOT_READY` if the cell has not been configured as
  ready. Does not modify `out_counts`.
- Returns `ErrorCode::OK` and writes the raw count to `out_counts` on success.

#### `CellSensor::read_temp_raw(uint8_t cell, int32_t& out_counts) -> ErrorCode`

Reads the raw temperature ADC count for the given cell. Same error behavior as
`read_voltage_raw`.

#### `CellSensor::is_ready(uint8_t cell) -> bool`

Returns `true` if the cell has been configured as ready, `false` otherwise. Returns
`false` for out-of-range cells.

---

## Monitoring Layer (`monitoring/`)

### `monitoring/cell_monitor.h` and `monitoring/cell_monitor.cpp`

`CellMonitor` wraps a `CellSensor` reference and converts raw ADC counts into
engineering units. It does not own the `CellSensor` — it holds a reference to one
provided at construction.

Conversions (integer arithmetic, truncating division):

- Voltage: `out_mv = (raw_counts * 5000) / 4095` — 12-bit ADC over a 5000 mV reference.
- Temperature: `out_dc = (raw_counts * 1650) / 4095 - 400` — linear sensor spanning
  −40.0 °C to +125.0 °C in deci-degrees.

#### Constructor

```cpp
CellMonitor(CellSensor& sensor)
```

Stores a reference to `sensor`.

#### `CellMonitor::to_millivolts(int32_t raw_counts, int32_t& out_mv) -> ErrorCode`

Converts a raw voltage count to millivolts.

- Returns `ErrorCode::HARDWARE_FAULT` if `raw_counts` is outside the physical ADC
  range `0..ADC_MAX_COUNTS`. Does not modify `out_mv`.
- Returns `ErrorCode::OK` and writes `(raw_counts * 5000) / 4095` to `out_mv`.

#### `CellMonitor::to_deci_celsius(int32_t raw_counts, int32_t& out_dc) -> ErrorCode`

Converts a raw temperature count to deci-degrees-Celsius.

- Returns `ErrorCode::HARDWARE_FAULT` if `raw_counts` is outside `0..ADC_MAX_COUNTS`.
  Does not modify `out_dc`.
- Returns `ErrorCode::OK` and writes `(raw_counts * 1650) / 4095 - 400` to `out_dc`.

#### `CellMonitor::read_cell_voltage(uint8_t cell, int32_t& out_mv) -> ErrorCode`

Reads the raw voltage count from the HAL and converts it to millivolts. This is the
supervision layer's entry point for voltage.

- Returns `ErrorCode::INVALID_ARGUMENT` if `cell` is out of range. Does not modify
  `out_mv`.
- Propagates any error from `read_voltage_raw` unchanged. Does not modify `out_mv`.
- Propagates `ErrorCode::HARDWARE_FAULT` from conversion if the raw count is out of
  physical range. Does not modify `out_mv`.
- Returns `ErrorCode::OK` and writes the converted millivolt value to `out_mv`.

#### `CellMonitor::read_cell_temp(uint8_t cell, int32_t& out_dc) -> ErrorCode`

Reads the raw temperature count from the HAL and converts it to deci-degrees-
Celsius. Same error behavior as `read_cell_voltage`.

### `monitoring/fault_manager.h` and `monitoring/fault_manager.cpp`

`FaultManager` records per-cell faults based on converted measurements.

#### Constructor

```cpp
FaultManager()
```

Initializes all cells to no fault recorded.

#### `FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) -> ErrorCode`

Evaluates the converted values against the safety thresholds and records the
corresponding fault for the cell.

- Returns `ErrorCode::INVALID_ARGUMENT` if `cell` is out of range. No state change.
- A voltage strictly greater than `OVER_VOLTAGE_MV` is an `OVER_VOLTAGE` fault.
- A voltage strictly less than `UNDER_VOLTAGE_MV` is an `UNDER_VOLTAGE` fault.
- A temperature strictly greater than `OVER_TEMP_DC` is an `OVER_TEMP` fault.
- If more than one threshold is exceeded in a single call, precedence is
  `OVER_VOLTAGE`, then `UNDER_VOLTAGE`, then `OVER_TEMP`.
- Returns `ErrorCode::OK` for any in-range cell, whether or not a fault was recorded.

#### `FaultManager::get_cell_fault(uint8_t cell) -> FaultType`

Returns the recorded fault for the cell. Returns `FaultType::NONE` if no fault is
recorded or if `cell` is out of range.

#### `FaultManager::has_any_fault() -> bool`

Returns `true` if any cell has a recorded fault.

#### `FaultManager::fault_count() -> uint8_t`

Returns the number of cells that currently have a recorded fault.

#### `FaultManager::reset_faults() -> void`

Clears all recorded faults.

---

## Supervision Layer (`supervision/`)

### `supervision/battery_supervisor.h` and `supervision/battery_supervisor.cpp`

`BatterySupervisor` orchestrates the poll cycle and owns the contactor decision. It
does not own the `CellMonitor` or `FaultManager` — it holds references provided at
construction. It must not include any `hal/` headers.

#### Constructor

```cpp
BatterySupervisor(CellMonitor& monitor, FaultManager& fault_manager)
```

Stores the references. Initializes the last-voltage cache to all zeros, with all
entries marked invalid.

#### `BatterySupervisor::poll_cell(uint8_t cell) -> ErrorCode`

Acquires the cell's voltage and temperature via `monitor`, feeds them to
`fault_manager.update_cell`, and caches the voltage for diagnostic queries.

- Returns `ErrorCode::INVALID_ARGUMENT` if `cell` is out of range. No state change.
- If `read_cell_voltage` or `read_cell_temp` fails, returns that error code
  immediately. The cache is not modified and `update_cell` is not called.
- On success, calls `update_cell(cell, voltage_mv, temp_dc)`, stores `voltage_mv`
  in the cache for `cell`, marks the cache entry valid, and returns `ErrorCode::OK`.

#### `BatterySupervisor::poll_all() -> ErrorCode`

Calls `poll_cell` for every cell from 0 to `CELL_COUNT - 1` in order.

- Returns the first non-OK error code immediately, without polling further cells.
- Returns `ErrorCode::OK` if every cell polled successfully.

#### `BatterySupervisor::get_last_voltage(uint8_t cell, int32_t& out_mv) -> ErrorCode`

Returns the most recent cached voltage for the cell.

- Returns `ErrorCode::INVALID_ARGUMENT` if `cell` is out of range. Does not modify
  `out_mv`.
- Returns `ErrorCode::SENSOR_NOT_READY` if no successful poll has completed for
  this cell yet. Does not modify `out_mv`.
- Returns `ErrorCode::OK` and writes the cached millivolt value to `out_mv`.

#### `BatterySupervisor::is_contactor_closed() -> bool`

Returns `true` if and only if no cell has a recorded fault. The contactor decision
derives from `fault_manager` state only.

#### `BatterySupervisor::request_reset() -> void`

Forwards the reset request to `fault_manager.reset_faults()`.

---

## Build System

`CMakeLists.txt` at the root. Compiles all three layers as a single static library
`bms`. Links the GTest test executable against it.

```cmake
cmake_minimum_required(VERSION 3.16)
project(bms CXX)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(bms
    hal/cell_sensor.cpp
    monitoring/cell_monitor.cpp
    monitoring/fault_manager.cpp
    supervision/battery_supervisor.cpp
)
target_include_directories(bms PUBLIC ${CMAKE_SOURCE_DIR})
```

Include directives use layer-prefixed paths from the project root, e.g.
`#include "hal/cell_sensor.h"`, `#include "common/error_code.h"`.

---

## Module-Level Conventions

- No `printf` or `std::cout` in library code.
- All integer variables: fixed-width types from `<cstdint>`.
- All engineering-unit values are integers: millivolts and deci-degrees-Celsius.
- All private data members end with a trailing underscore (`faults_`, `ready_`).
- All member function definitions in `.cpp` files — headers are declarations only.
- Fixed-size member storage uses `std::array`, not C-style arrays.
- Scoped enums (`enum class`) only.
- `nullptr`, not `NULL` or `0`, for null pointers.
- `static constexpr` for compile-time constants, not `#define`.
- No `new` or `delete` — stack allocation only.
- No virtual functions.
