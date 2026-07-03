// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
ErrorCode CellSensor::read_voltage_raw(uint8_t cell, int32_t& out_counts) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!ready_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_counts = raw_voltage_[cell];
    return ErrorCode::OK;
}
