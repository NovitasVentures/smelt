// Shape 4 (Clean): delegating query returns !fault_manager_.has_any_fault().
// No member assignment in this function body.
bool BatterySupervisor::is_contactor_closed() {
    return !fault_manager_.has_any_fault();
}
