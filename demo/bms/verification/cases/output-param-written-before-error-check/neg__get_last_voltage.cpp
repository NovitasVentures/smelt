// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
ErrorCode BatterySupervisor::get_last_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!valid_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_mv = last_mv_[cell];
    return ErrorCode::OK;
}
