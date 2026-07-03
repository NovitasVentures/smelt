// VIOLATION: out_counts initialized before the ready check that can fail (SAD 6.5).
ErrorCode CellSensor::read_temp_raw(uint8_t cell, int32_t& out_counts) {
    out_counts = 0;
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (!ready_[cell]) {
        return ErrorCode::SENSOR_NOT_READY;
    }
    out_counts = raw_temp_[cell];
    return ErrorCode::OK;
}
