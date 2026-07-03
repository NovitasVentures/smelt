// Shape 4 (Clean): reset-flavored name delegates; body contains no fault
// member assignment at all.
void BatterySupervisor::request_reset() {
    fault_manager_.reset_faults();
}
