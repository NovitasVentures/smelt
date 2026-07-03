// Shape 3 (Clean — FP! trap): query initializes a local FaultType to NONE.
// Local variables are always clean, even named "current" and set to NONE.
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    FaultType current = FaultType::NONE;
    if (cell < CELL_COUNT) {
        current = faults_[cell];
    }
    return current;
}
