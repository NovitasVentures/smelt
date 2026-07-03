// Shape 1 (Clean — FP! trap): const-style query loops over a member array
// and returns a bool. Mutates nothing.
bool FaultManager::has_any_fault() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            return true;
        }
    }
    return false;
}
