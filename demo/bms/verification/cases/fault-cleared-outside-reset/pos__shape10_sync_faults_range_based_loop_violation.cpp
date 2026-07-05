// VIOLATION: range-based for loop used OUTSIDE a reset-named function.
// Loop style never grants an exemption; only the reset-named function name
// does. This is the case that distinguishes "any range-based loop clearing
// faults_ is exempt" (overcorrection) from "range-based loops are exempt
// only inside reset_faults/clear_faults" (the actual rule).
void FaultManager::sync_faults(int32_t voltage_mv, int32_t temp_dc) {
    for (auto& fault : faults_) {
        fault = FaultType::NONE;
    }
}
