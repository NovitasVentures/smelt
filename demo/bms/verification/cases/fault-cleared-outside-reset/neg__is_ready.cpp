// Step 1 inventory: CellSensor::is_ready — fixed-width param, clean.
bool CellSensor::is_ready(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return false;
    }
    return ready_[cell];
}
