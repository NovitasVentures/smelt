// Shape 8 (Clean — FP! trap): reset_faults using a range-based for loop over
// std::array instead of an indexed loop. Same exemption applies regardless
// of loop syntax.
void FaultManager::reset_faults() {
    for (auto& fault : faults_) {
        fault = FaultType::NONE;
    }
}
