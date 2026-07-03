// VIOLATION (shape 7): getter updates a bookkeeping member — lazy cache
// refresh inside a query, mutating last_mv_ from a get_-named function.
ErrorCode BatterySupervisor::get_last_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t mv = 0;
    if (monitor_.read_cell_voltage(cell, mv) == ErrorCode::OK) {
        last_mv_[cell] = mv;
    }
    out_mv = last_mv_[cell];
    return ErrorCode::OK;
}
