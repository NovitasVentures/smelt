// VIOLATION: bare int for a raw ADC count and converted output (ADR-002).
ErrorCode CellMonitor::to_millivolts(int raw_counts, int& out_mv) {
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    out_mv = (raw_counts * 5000) / 4095;
    return ErrorCode::OK;
}
