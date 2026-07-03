// Shape 3 (Clean): HAL read bounds-checks the cell index, not a raw reading.
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
