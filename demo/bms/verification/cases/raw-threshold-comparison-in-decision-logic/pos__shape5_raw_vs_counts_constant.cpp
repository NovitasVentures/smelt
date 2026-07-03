// VIOLATION (shape 5): decision function compares a raw identifier against a
// named counts-domain constant instead of an engineering-unit threshold.
static constexpr int32_t OVER_VOLTAGE_COUNTS = 3440;

ErrorCode FaultManager::update_cell(uint8_t cell, int32_t raw_counts, int32_t temp_dc) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (raw_counts > OVER_VOLTAGE_COUNTS) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    }
    return ErrorCode::OK;
}
