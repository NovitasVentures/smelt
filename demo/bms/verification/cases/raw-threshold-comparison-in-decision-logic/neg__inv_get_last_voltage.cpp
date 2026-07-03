// Step 1 inventory: BatterySupervisor::get_last_voltage — fixed-width types, clean.
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
