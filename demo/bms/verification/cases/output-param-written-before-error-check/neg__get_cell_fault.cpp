// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
// New shape for this specialist: value-return query, no output parameter.
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return FaultType::NONE;
    }
    return faults_[cell];
}
