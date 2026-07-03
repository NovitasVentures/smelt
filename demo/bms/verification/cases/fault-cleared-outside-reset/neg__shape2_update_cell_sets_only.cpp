// Shape 2 (Clean): evaluation function sets a fault value on threshold
// exceedance with no else-clear. Setting faults is always permitted.
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
