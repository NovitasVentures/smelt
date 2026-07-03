// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
bool CellSensor::is_ready(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return false;
    }
    return ready_[cell];
}
