// Shape 1 (Clean — FP! trap): reset function clears fault members in a loop.
// The clearing assignment is legal here because the function name is reset_faults.
void FaultManager::reset_faults() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}
