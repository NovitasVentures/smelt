// Shape 1 (Clean — FP! trap): decision function compares engineering-unit
// identifiers (voltage_mv, temp_dc) against named thresholds.
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    } else if (voltage_mv < UNDER_VOLTAGE_MV) {
        faults_[cell] = FaultType::UNDER_VOLTAGE;
    } else if (temp_dc > OVER_TEMP_DC) {
        faults_[cell] = FaultType::OVER_TEMP;
    }
    return ErrorCode::OK;
}
