// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
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
