// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
// New shape for this specialist: local accumulator returning uint8_t.
uint8_t FaultManager::fault_count() {
    uint8_t count = 0U;
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            ++count;
        }
    }
    return count;
}
