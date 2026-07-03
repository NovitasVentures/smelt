// VIOLATION (shape 6): supervision shortcut — poll reads raw counts and
// threshold-checks them before any conversion to engineering units.
ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {
    int32_t raw_counts = 0;
    ErrorCode status = sensor_.read_voltage_raw(cell, raw_counts);
    if (status != ErrorCode::OK) {
        return status;
    }
    if (raw_counts > 3440) {
        fault_manager_.update_cell(cell, 9999, 0);
    }
    return ErrorCode::OK;
}
