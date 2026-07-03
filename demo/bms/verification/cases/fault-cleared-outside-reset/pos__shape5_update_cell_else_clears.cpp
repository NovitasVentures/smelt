// VIOLATION (shape 5): update_cell else-clears the fault when the reading is
// in range — un-latches on recovery, violating SAD 6.2.
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    } else {
        faults_[cell] = FaultType::NONE;
    }
    return ErrorCode::OK;
}
