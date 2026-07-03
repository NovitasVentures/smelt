// Shape 2 (Clean — FP! trap): query accumulates into a local (++count) and
// returns it. Must classify negative despite the increment.
uint8_t FaultManager::fault_count() {
    uint8_t count = 0U;
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            ++count;
        }
    }
    return count;
}
