// Shape 5 (Clean): command function (non-query name) mutates members freely.
void CellSensor::configure(uint8_t cell, int32_t raw_voltage, int32_t raw_temp, bool ready) {
    if (cell >= CELL_COUNT) {
        return;
    }
    raw_voltage_[cell] = raw_voltage;
    raw_temp_[cell] = raw_temp;
    ready_[cell] = ready;
}
