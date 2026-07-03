// Step 1 inventory: CellSensor::configure — fixed-width params, clean.
void CellSensor::configure(uint8_t cell, int32_t raw_voltage, int32_t raw_temp, bool ready) {
    if (cell >= CELL_COUNT) {
        return;
    }
    raw_voltage_[cell] = raw_voltage;
    raw_temp_[cell] = raw_temp;
    ready_[cell] = ready;
}
