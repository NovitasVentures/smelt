// VIOLATION: out_mv written from the cache before checking whether the cache
// entry is valid (SAD 6.5).
ErrorCode BatterySupervisor::get_last_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    out_mv = last_mv_[cell];
    if (!valid_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    return ErrorCode::OK;
}
