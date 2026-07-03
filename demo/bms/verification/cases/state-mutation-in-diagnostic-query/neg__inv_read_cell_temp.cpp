// Step 1 inventory: CellMonitor::read_cell_temp — fixed-width types, clean.
ErrorCode CellMonitor::read_cell_temp(uint8_t cell, int32_t& out_dc) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t raw_counts = 0;
    ErrorCode status = sensor_.read_temp_raw(cell, raw_counts);
    if (status != ErrorCode::OK) {
        return status;
    }
    return to_deci_celsius(raw_counts, out_dc);
}
