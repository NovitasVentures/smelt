// Step 1 inventory: CellSensor::read_temp_raw — fixed-width types, clean.
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
