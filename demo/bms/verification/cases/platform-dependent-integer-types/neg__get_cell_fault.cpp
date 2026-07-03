// Step 1 inventory: FaultManager::get_cell_fault — fixed-width param, clean.
// New shape for this specialist: value-return query, no output parameter.
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return FaultType::NONE;
    }
    return faults_[cell];
}
