// VIOLATION: out_counts initialized at top of function before error checks (SAD 6.5).
ErrorCode CellSensor::read_voltage_raw(uint8_t cell, int32_t& out_counts) {
    out_counts = 0;
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!ready_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_counts = raw_voltage_[cell];
    return ErrorCode::OK;
}
