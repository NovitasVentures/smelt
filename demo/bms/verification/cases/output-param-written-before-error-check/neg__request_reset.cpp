// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
void BatterySupervisor::request_reset() {
    fault_manager_.reset_faults();
}
