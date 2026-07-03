// VIOLATION: bare int/unsigned instead of fixed-width cstdint types (ADR-002).
ErrorCode CellSensor::read_voltage_raw(unsigned cell, int& out_counts) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!ready_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_counts = raw_voltage_[cell];
    return ErrorCode::OK;
}
