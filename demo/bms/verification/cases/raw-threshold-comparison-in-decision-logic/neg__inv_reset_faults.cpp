// Step 1 inventory: FaultManager::reset_faults — fixed-width loop counter, clean.
void FaultManager::reset_faults() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}
