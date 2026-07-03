// Step 1 inventory (FP! trap): conversion function range-checks raw_counts —
// clean because the comparison lives inside the conversion function.
ErrorCode CellMonitor::to_deci_celsius(int32_t raw_counts, int32_t& out_dc) {
    if ((raw_counts < 0) || (raw_counts > ADC_MAX_COUNTS)) {
        return ErrorCode::HARDWARE_FAULT;
    }
    out_dc = (raw_counts * 1650) / 4095 - 400;
    return ErrorCode::OK;
}
