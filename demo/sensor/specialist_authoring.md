# Output Parameter Purity — Specialist Authoring Guide

This document is the method inventory and eval_on authoring record for the
`output-param-written-before-error-check`, `output-param-written-on-error-path`,
and `platform-dependent-integer-types` Crasis specialists. It must be complete
before the first `smelt arch-build` run. See `demo/crasis/specialist_authoring.md`
for the full process rationale and cost discipline.

---

## Principle Summary

A function that returns an `ErrorCode` and writes a result via an output parameter
(reference or pointer) must not write to that output parameter on error return paths.
The output parameter is written only after all error conditions are confirmed absent.

---

## Method Inventory

Every method in the sensor pipeline that has an output parameter. Classified before
building any specialist.

| Method | Out-param | Return type | Classification | FP Risk |
|---|---|---|---|---|
| `SensorDriver::read_raw` | `int32_t& out_raw` | `ErrorCode` | **Critical — multiple error paths, must not write on any of them** | HIGH: error paths come first, success write is last |
| `SensorProcessor::calibrate` | `float& out_calibrated` | `ErrorCode` | **Critical** | MEDIUM |
| `SensorProcessor::filter` | `float& out_filtered` | `ErrorCode` | **Critical — null and zero-count errors** | HIGH: null-check before write looks clean but some LLMs init out_filtered = 0.0f at top |
| `SensorProcessor::acquire` | `float& out_value` | `ErrorCode` | **Critical — 3 error paths** | HIGH: complex branching invites early init |
| `SensorDispatcher::get_last_reading` | `float& out_value` | `ErrorCode` | **Critical** | MEDIUM |
| `SensorDriver::configure` | none | `void` | clean (no out-param, no error code) | N/A |
| `SensorDriver::is_ready` | none | `bool` | clean (no out-param, value return) | HIGH FP: looks like it should be a violation but is not |
| `SensorProcessor::set_calibration` | none | `void` | clean (no out-param) | N/A |
| `SensorDispatcher::sample_and_dispatch` | none | `ErrorCode` | clean (no out-param — communicates via cache + return code) | HIGH FP: has multiple error returns, no out-param |

---

## Shape Classification for eval_on

Seven distinct shapes. Each must be covered before build.

### Shape 1 — Clean: error early-return, out-param untouched

```cpp
// CLEAN: out_raw not touched on error paths
ErrorCode read_raw(SensorId id, int32_t& out_raw) {
    if (id >= SENSOR_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!state_[static_cast<uint8_t>(id)].ready) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_raw = state_[static_cast<uint8_t>(id)].raw_value;
    return ErrorCode::OK;
}
```

### Shape 2 — Violation: out-param initialized at top before error checks

```cpp
// VIOLATION: out_raw = 0 before error checks — writes on error path
ErrorCode read_raw(SensorId id, int32_t& out_raw) {
    out_raw = 0;
    if (id >= SENSOR_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!state_[static_cast<uint8_t>(id)].ready) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_raw = state_[static_cast<uint8_t>(id)].raw_value;
    return ErrorCode::OK;
}
```

### Shape 3 — Clean: success path only, single write

```cpp
// CLEAN: single write at success, no error paths
ErrorCode calibrate(SensorId id, int32_t raw, float& out_calibrated) {
    if (static_cast<uint8_t>(id) >= SENSOR_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    out_calibrated = static_cast<float>(raw) * scale_[static_cast<uint8_t>(id)]
                     + offset_[static_cast<uint8_t>(id)];
    return ErrorCode::OK;
}
```

### Shape 4 — Violation: one of two error paths writes the out-param

```cpp
// VIOLATION: out_value written on SENSOR_NOT_READY path but not on SENSOR_FAULT path
ErrorCode acquire(SensorId id, float& out_value) {
    int32_t raw{0};
    ErrorCode rc = driver_.read_raw(id, raw);
    if (rc == ErrorCode::SENSOR_NOT_READY) {
        out_value = 0.0f;                  // writes on error path
        return ErrorCode::SENSOR_NOT_READY;
    }
    if (rc != ErrorCode::OK) {
        return ErrorCode::SENSOR_FAULT;    // does not write — inconsistent
    }
    ErrorCode cal_rc = calibrate(id, raw, out_value);
    if (cal_rc != ErrorCode::OK) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    return ErrorCode::OK;
}
```

### Shape 5 — Violation: out-param written in error branch, then overwritten on success

```cpp
// VIOLATION: out_filtered assigned inside error branch before early return is added
ErrorCode filter(const float* samples, uint8_t count, float& out_filtered) {
    out_filtered = 0.0f;                   // written here...
    if (samples == nullptr || count == 0U) {
        return ErrorCode::INVALID_ARGUMENT; // ...and this returns, so caller sees 0.0f
    }
    float sum{0.0f};
    for (uint8_t i = 0U; i < count; ++i) {
        sum += samples[i];
    }
    out_filtered = sum / static_cast<float>(count);  // overwritten on success
    return ErrorCode::OK;
}
```

### Shape 6 — HIGH RISK FP: function returns value directly, no out-param

```cpp
// CLEAN: no out-param — returns bool directly. Must NOT fire.
bool is_ready(SensorId id) {
    if (static_cast<uint8_t>(id) >= SENSOR_COUNT) {
        return false;
    }
    return state_[static_cast<uint8_t>(id)].ready;
}
```

### Shape 7 — HIGH RISK FP: function has error returns but no out-param

```cpp
// CLEAN: ErrorCode return only, no out-param. Must NOT fire.
ErrorCode sample_and_dispatch(SensorId id, float threshold) {
    float samples[SAMPLE_COUNT]{};
    for (uint8_t i = 0U; i < SAMPLE_COUNT; ++i) {
        ErrorCode rc = processor_.acquire(id, samples[i]);
        if (rc != ErrorCode::OK) {
            return rc;
        }
    }
    float filtered{0.0f};
    ErrorCode frc = processor_.filter(samples, SAMPLE_COUNT, filtered);
    if (frc != ErrorCode::OK) {
        return ErrorCode::SENSOR_FAULT;
    }
    cache_[static_cast<uint8_t>(id)] = {filtered, true};
    return (filtered > threshold) ? ErrorCode::THRESHOLD_EXCEEDED : ErrorCode::OK;
}
```

---

## Paired Minimal Examples for HIGH RISK FP Shapes

For each HIGH RISK FP shape, a paired violation that differs by exactly the mutation.
This teaches the model to key on out-param mutation, not function structure.

### Pair for Shape 6 (bool return, no out-param)

```cpp
// CLEAN version (Shape 6) — bool return, no out-param
bool is_ready(SensorId id) {
    if (static_cast<uint8_t>(id) >= SENSOR_COUNT) { return false; }
    return state_[static_cast<uint8_t>(id)].ready;
}

// How this would become a violation (hypothetical, not in spec):
// If the return type were ErrorCode and it had an out-param, writing it on error would be a violation.
// The classifier must learn: the absence of an out-param reference/pointer means no violation is possible.
```

### Pair for Shape 7 (ErrorCode return, no out-param)

```cpp
// CLEAN (Shape 7) — multiple error returns, no out-param
ErrorCode sample_and_dispatch(SensorId id, float threshold) {
    float samples[3]{};
    for (uint8_t i = 0U; i < 3U; ++i) {
        ErrorCode rc = processor_.acquire(id, samples[i]);
        if (rc != ErrorCode::OK) { return rc; }
    }
    // ... (no out-param, clean)
    return ErrorCode::OK;
}

// VIOLATION that differs only by adding an out-param and writing it on error:
ErrorCode sample_and_dispatch(SensorId id, float threshold, float& out_debug) {
    out_debug = -1.0f;                     // <-- write on entry, before error check
    float samples[3]{};
    for (uint8_t i = 0U; i < 3U; ++i) {
        ErrorCode rc = processor_.acquire(id, samples[i]);
        if (rc != ErrorCode::OK) { return rc; }  // <-- returns with out_debug = -1.0f
    }
    out_debug = 0.0f;
    return ErrorCode::OK;
}
```

---

## Pre-Build Verification Checklist

Before running `smelt arch-build`:

- [ ] All 7 shapes above are represented in eval_on
- [ ] Shape 6 (bool-return, no out-param) has a corresponding eval_on clean example
- [ ] Shape 7 (ErrorCode, no out-param) has a corresponding eval_on clean example
- [ ] Every violation shape has a paired clean example differing by exactly the mutation
- [ ] Run `crasis classify` on all 7 shapes in isolation and confirm:
  - Shapes 1, 3, 6, 7 score < 0.80 (clean)
  - Shapes 2, 4, 5 score > 0.85 (violation)
- [ ] If any clean shape scores > 0.80, add more eval_on negatives for that shape before proceeding

---

## Build History

| Build | Problem | Fix |
|---|---|---|
| — | (not yet built) | — |

Update this table after each build attempt.
