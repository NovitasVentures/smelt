// Step 1 inventory: BatterySupervisor::poll_all — fixed-width loop counter, clean.
// New shape for this specialist: loop of ErrorCode-returning calls.
ErrorCode BatterySupervisor::poll_all() {
    for (uint8_t cell = 0U; cell < CELL_COUNT; ++cell) {
        ErrorCode status = poll_cell(cell);
        if (status != ErrorCode::OK) {
            return status;
        }
    }
    return ErrorCode::OK;
}
