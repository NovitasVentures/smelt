// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
BatterySupervisor::BatterySupervisor(CellMonitor& monitor, FaultManager& fault_manager)
    : monitor_(monitor), fault_manager_(fault_manager) {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        last_mv_[i] = 0;
        valid_[i] = false;
    }
}
