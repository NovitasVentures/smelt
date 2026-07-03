// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
CellSensor::CellSensor() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        raw_voltage_[i] = 0;
        raw_temp_[i] = 0;
        ready_[i] = false;
    }
}
