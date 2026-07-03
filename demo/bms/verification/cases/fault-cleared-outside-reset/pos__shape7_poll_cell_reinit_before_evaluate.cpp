// VIOLATION (shape 7): poll function unconditionally re-initializes the fault
// member before evaluating, clearing any latched fault every poll cycle.
ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t voltage_mv = 0;
    int32_t temp_dc = 0;
    ErrorCode status = monitor_.read_cell_voltage(cell, voltage_mv);
    if (status != ErrorCode::OK) {
        return status;
    }
    status = monitor_.read_cell_temp(cell, temp_dc);
    if (status != ErrorCode::OK) {
        return status;
    }
    fault_manager_.reset_faults();
    fault_manager_.update_cell(cell, voltage_mv, temp_dc);
    last_mv_[cell] = voltage_mv;
    valid_[cell] = true;
    return ErrorCode::OK;
}
