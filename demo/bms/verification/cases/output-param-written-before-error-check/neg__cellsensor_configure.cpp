// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
void CellSensor::configure(uint8_t cell, int32_t raw_voltage, int32_t raw_temp, bool ready) {
    if (cell >= CELL_COUNT) {
        return;
    }
    raw_voltage_[cell] = raw_voltage;
    raw_temp_[cell] = raw_temp;
    ready_[cell] = ready;
}
