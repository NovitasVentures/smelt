// Shape 9 (Clean — FP! trap): clear_faults using a range-based for loop,
// same exemption as reset_faults.
void FaultManager::clear_faults() {
    for (auto& fault : faults_) {
        fault = FaultType::NONE;
    }
}
