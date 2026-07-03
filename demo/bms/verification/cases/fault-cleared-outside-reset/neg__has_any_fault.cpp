// Step 1 inventory: FaultManager::has_any_fault — fixed-width loop counter, clean.
bool FaultManager::has_any_fault() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            return true;
        }
    }
    return false;
}
