// VIOLATION (shape 6): getter clears the fault member after reading it.
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    FaultType result = faults_[cell];
    faults_[cell] = FaultType::NONE;
    return result;
}
