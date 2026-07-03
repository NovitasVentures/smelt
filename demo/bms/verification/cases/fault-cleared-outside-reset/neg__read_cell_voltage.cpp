// Step 1 inventory: CellMonitor::read_cell_voltage — fixed-width types, clean.
ErrorCode CellMonitor::read_cell_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t raw_counts = 0;
    ErrorCode status = sensor_.read_voltage_raw(cell, raw_counts);
    if (status != ErrorCode::OK) {
        return status;
    }
    return to_millivolts(raw_counts, out_mv);
}
