// Step 1 inventory: FaultManager::FaultManager() — fixed-width init, clean.
FaultManager::FaultManager() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}
