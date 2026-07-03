// Step 1 inventory (FP! trap, same pattern as read_voltage_raw): HAL read
// bounds-checks the cell index only — no raw-value threshold comparison.
ErrorCode CellSensor::read_temp_raw(uint8_t cell, int32_t& out_counts) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!ready_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_counts = raw_temp_[cell];
    return ErrorCode::OK;
}
