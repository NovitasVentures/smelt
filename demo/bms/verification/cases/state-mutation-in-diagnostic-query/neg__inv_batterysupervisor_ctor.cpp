// Step 1 inventory: BatterySupervisor::BatterySupervisor(CellMonitor&, FaultManager&) — clean.
BatterySupervisor::BatterySupervisor(CellMonitor& monitor, FaultManager& fault_manager)
    : monitor_(monitor), fault_manager_(fault_manager) {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        last_mv_[i] = 0;
        valid_[i] = false;
    }
}
