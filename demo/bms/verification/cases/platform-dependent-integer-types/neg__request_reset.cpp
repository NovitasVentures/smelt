// Step 1 inventory: BatterySupervisor::request_reset — no integer types, clean.
void BatterySupervisor::request_reset() {
    fault_manager_.reset_faults();
}
