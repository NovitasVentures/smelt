// Shape 3 (Clean — FP! trap): query indexes a member array and returns the
// element — reading a member is not mutating it.
bool CellSensor::is_ready(uint8_t cell) {
    if (cell >= CELL_COUNT) {
        return false;
    }
    return ready_[cell];
}
