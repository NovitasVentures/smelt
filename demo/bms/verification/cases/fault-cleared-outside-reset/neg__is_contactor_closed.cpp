// Step 1 inventory: BatterySupervisor::is_contactor_closed — no integer types, clean.
bool BatterySupervisor::is_contactor_closed() {
    return !fault_manager_.has_any_fault();
}
