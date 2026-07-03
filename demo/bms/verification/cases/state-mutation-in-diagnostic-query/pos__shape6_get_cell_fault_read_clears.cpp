// VIOLATION (shape 6): getter clears the member it reports — read-clears the
// fault, consuming it. Also violates P2 (SAD 6.2); overlap is expected and safe.
FaultType FaultManager::get_cell_fault(uint8_t cell) {
    FaultType result = faults_[cell];
    faults_[cell] = FaultType::NONE;
    return result;
}
