// Step 1 inventory: CellMonitor::to_millivolts — fixed-width types, clean.
ErrorCode CellMonitor::to_millivolts(int32_t raw_counts, int32_t& out_mv) {
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    out_mv = (raw_counts * 5000) / 4095;
    return ErrorCode::OK;
}
