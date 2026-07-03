// VIOLATION: out_mv zero-initialized up front, clobbering the caller's sentinel
// even when a subsequent error path is taken (SAD 6.5).
ErrorCode CellMonitor::read_cell_voltage(uint8_t cell, int32_t& out_mv) {
    out_mv = 0;
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
