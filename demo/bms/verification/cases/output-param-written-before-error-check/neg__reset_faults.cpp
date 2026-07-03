// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
void FaultManager::reset_faults() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}
