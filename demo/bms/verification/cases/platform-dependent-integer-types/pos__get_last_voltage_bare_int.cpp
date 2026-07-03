// VIOLATION: bare int cache lookup and output param instead of int32_t (ADR-002).
ErrorCode BatterySupervisor::get_last_voltage(unsigned cell, int& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!valid_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_mv = last_mv_[cell];
    return ErrorCode::OK;
}
