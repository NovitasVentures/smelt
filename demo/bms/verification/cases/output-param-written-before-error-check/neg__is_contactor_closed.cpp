// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
bool BatterySupervisor::is_contactor_closed() {
    return !fault_manager_.has_any_fault();
}
