// VIOLATION: bare int loop counter and return type instead of uint8_t (ADR-002).
int FaultManager::fault_count() {
    int count = 0;
    for (int i = 0; i < CELL_COUNT; ++i) {
        if (faults_[i] != FaultType::NONE) {
            ++count;
        }
    }
    return count;
}
