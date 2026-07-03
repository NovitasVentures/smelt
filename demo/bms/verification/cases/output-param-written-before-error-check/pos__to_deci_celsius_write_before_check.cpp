// VIOLATION: out_dc written before the range check that can still fail (SAD 6.5).
ErrorCode CellMonitor::to_deci_celsius(int32_t raw_counts, int32_t& out_dc) {
    out_dc = (raw_counts * 1650) / 4095 - 400;
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    return ErrorCode::OK;
}
