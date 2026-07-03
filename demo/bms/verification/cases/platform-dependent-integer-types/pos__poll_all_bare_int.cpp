// VIOLATION: bare int loop counter over CELL_COUNT instead of uint8_t (ADR-002).
ErrorCode BatterySupervisor::poll_all() {
    for (int cell = 0; cell < CELL_COUNT; ++cell) {
        ErrorCode status = poll_cell(cell);
        if (status != ErrorCode::OK) {
            return status;
        }
    }
    return ErrorCode::OK;
}
