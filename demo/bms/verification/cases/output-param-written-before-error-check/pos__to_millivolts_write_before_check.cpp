// VIOLATION: out_mv written before the range check that can still fail (SAD 6.5).
ErrorCode CellMonitor::to_millivolts(int32_t raw_counts, int32_t& out_mv) {
    out_mv = (raw_counts * 5000) / 4095;
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    return ErrorCode::OK;
}
