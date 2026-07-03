// Shape 2 (Clean — FP! trap, in-spec): conversion function range-checks
// raw_counts against 0..ADC_MAX_COUNTS. This exact body appears in bms_spec.md
// and must classify negative.
ErrorCode CellMonitor::to_millivolts(int32_t raw_counts, int32_t& out_mv) {
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    out_mv = (raw_counts * 5000) / 4095;
    return ErrorCode::OK;
}
