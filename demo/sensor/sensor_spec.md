# Embedded Sensor Pipeline — Implementation Spec

Implement a three-layer C++14 library: `hal/`, `processing/`, and `application/`. Each
layer lives in its own directory. All headers use `#pragma once`. All integers use
`<cstdint>` fixed-width types. No exceptions — all errors communicated via `ErrorCode`.

---

## Shared Type: `ErrorCode`

Defined in `common/error_code.h`. All layers include this header.

```cpp
#pragma once
#include <cstdint>

enum class ErrorCode : uint8_t {
    OK               = 0,
    SENSOR_FAULT     = 1,
    SENSOR_NOT_READY = 2,
    INVALID_ARGUMENT = 3,
    THRESHOLD_EXCEEDED = 4,
};
```

---

## Shared Type: `SensorId`

Defined in `common/sensor_id.h`.

```cpp
#pragma once
#include <cstdint>

enum class SensorId : uint8_t {
    ACCEL_X = 0,
    ACCEL_Y = 1,
    ACCEL_Z = 2,
    GYRO_X  = 3,
    GYRO_Y  = 4,
    GYRO_Z  = 5,
};

static constexpr uint8_t SENSOR_COUNT = 6U;
```

---

## HAL Layer (`hal/`)

### `hal/sensor_driver.h` and `hal/sensor_driver.cpp`

`SensorDriver` is the hardware abstraction for raw sensor register reads. It maintains
an internal state table for each of the six sensor axes. In the real system this would
talk to an SPI or I2C peripheral; in this implementation it uses a configurable internal
table that tests can inject values into.

#### Constructor

```cpp
SensorDriver()
```

Initializes all sensor slots to not-ready with raw value 0.

#### `SensorDriver::configure(SensorId id, int32_t raw_value, bool ready) -> void`

Sets the simulated raw reading and ready state for a given sensor. Used by tests to
inject known values. Not part of the operational interface.

- Does nothing if `id` is out of range.

#### `SensorDriver::read_raw(SensorId id, int32_t& out_raw) -> ErrorCode`

Reads the raw integer sample for the given sensor axis.

- Returns `ErrorCode::INVALID_ARGUMENT` if `id` is out of the valid range. Does not
  modify `out_raw`.
- Returns `ErrorCode::SENSOR_NOT_READY` if the sensor has not been configured as ready.
  Does not modify `out_raw`.
- Returns `ErrorCode::OK` and writes the raw sample to `out_raw` on success.

#### `SensorDriver::is_ready(SensorId id) -> bool`

Returns `true` if the sensor has been configured as ready, `false` otherwise. Returns
`false` for out-of-range IDs.

---

## Processing Layer (`processing/`)

### `processing/sensor_processor.h` and `processing/sensor_processor.cpp`

`SensorProcessor` wraps a `SensorDriver` reference and applies calibration and filtering.
It does not own the `SensorDriver` — it holds a reference to one provided at construction.

Calibration: `calibrated = raw * scale + offset` where `scale` and `offset` are
per-sensor coefficients stored internally. Default coefficients: `scale = 0.01f`,
`offset = 0.0f` for all sensors.

#### Constructor

```cpp
SensorProcessor(SensorDriver& driver)
```

Stores a reference to `driver`. Initializes calibration coefficients to defaults.

#### `SensorProcessor::set_calibration(SensorId id, float scale, float offset) -> void`

Sets the calibration scale and offset for a given sensor.

- Does nothing if `id` is out of range.
- Does nothing if `scale` is zero (would produce a degenerate calibration).

#### `SensorProcessor::calibrate(SensorId id, int32_t raw, float& out_calibrated) -> ErrorCode`

Applies calibration to a raw integer sample.

- Returns `ErrorCode::INVALID_ARGUMENT` if `id` is out of range. Does not modify
  `out_calibrated`.
- Returns `ErrorCode::OK` and writes `raw * scale[id] + offset[id]` to `out_calibrated`.

#### `SensorProcessor::filter(const float* samples, uint8_t count, float& out_filtered) -> ErrorCode`

Computes the arithmetic mean of `count` samples and writes it to `out_filtered`.

- Returns `ErrorCode::INVALID_ARGUMENT` if `samples` is null or `count` is zero. Does
  not modify `out_filtered`.
- Returns `ErrorCode::OK` and writes the mean of `samples[0..count-1]` to `out_filtered`.

#### `SensorProcessor::acquire(SensorId id, float& out_value) -> ErrorCode`

Reads a raw sample from the HAL, applies calibration, and writes the result to
`out_value`. This is the primary entry point for the application layer.

- Returns `ErrorCode::SENSOR_NOT_READY` if the sensor is not ready. Does not modify
  `out_value`.
- Returns `ErrorCode::SENSOR_FAULT` if `read_raw` returns any error other than
  `SENSOR_NOT_READY`. Does not modify `out_value`.
- Returns `ErrorCode::INVALID_ARGUMENT` if calibration fails. Does not modify
  `out_value`.
- Returns `ErrorCode::OK` and writes the calibrated value to `out_value` on success.

---

## Application Layer (`application/`)

### `application/sensor_dispatcher.h` and `application/sensor_dispatcher.cpp`

`SensorDispatcher` orchestrates multi-sample acquisition and threshold-based dispatch.
It does not own the `SensorProcessor` — it holds a reference to one provided at
construction. It must not include any `hal/` headers.

#### Constructor

```cpp
SensorDispatcher(SensorProcessor& processor)
```

Stores a reference to `processor`. Initializes the last-reading cache to all zeros,
with all entries marked invalid.

#### `SensorDispatcher::sample_and_dispatch(SensorId id, float threshold) -> ErrorCode`

Acquires `SAMPLE_COUNT` (3) consecutive readings for `id` via `processor.acquire()`,
computes their mean using `processor.filter()`, compares the filtered value against
`threshold`, stores the filtered value in the internal cache, and returns an appropriate
status code.

- If any call to `processor.acquire()` fails, returns that error code immediately
  without modifying the cache or calling `filter`. Does not modify any output parameter
  (this function has none — it communicates results through the cache and return code).
- If `processor.filter()` fails, returns `ErrorCode::SENSOR_FAULT`.
- If the filtered value exceeds `threshold` (strictly greater than), stores the value in
  the cache and returns `ErrorCode::THRESHOLD_EXCEEDED`.
- Otherwise stores the value in the cache and returns `ErrorCode::OK`.

`SAMPLE_COUNT` must be defined as a `static constexpr uint8_t` in the class body.

#### `SensorDispatcher::get_last_reading(SensorId id, float& out_value) -> ErrorCode`

Returns the most recent cached reading for `id`.

- Returns `ErrorCode::INVALID_ARGUMENT` if `id` is out of range. Does not modify
  `out_value`.
- Returns `ErrorCode::SENSOR_NOT_READY` if no reading has been successfully cached for
  `id` yet (i.e., `sample_and_dispatch` has not completed successfully for this sensor).
  Does not modify `out_value`.
- Returns `ErrorCode::OK` and writes the cached value to `out_value`.

---

## Build System

`CMakeLists.txt` at the root. Compiles all three layers as a single static library
`sensor_pipeline`. Links the GTest test executable against it.

```cmake
cmake_minimum_required(VERSION 3.16)
project(sensor_pipeline CXX)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sensor_pipeline
    hal/sensor_driver.cpp
    processing/sensor_processor.cpp
    application/sensor_dispatcher.cpp
)
target_include_directories(sensor_pipeline PUBLIC ${CMAKE_SOURCE_DIR})
```

---

## Module-Level Conventions

- No `printf` or `std::cout` in library code.
- All integer variables: fixed-width types from `<cstdint>`.
- `nullptr`, not `NULL` or `0`, for null pointers.
- `static constexpr` for compile-time constants, not `#define`.
- No `new` or `delete` — stack allocation only.
- No virtual functions.
