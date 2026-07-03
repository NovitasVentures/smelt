// VIOLATION (shape 4): decision function compares a raw identifier against a
// bare numeric literal — the 4200 mV threshold is baked into ADC counts.
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t raw_counts, int32_t temp_dc) {
    if (raw_counts > 3440) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    }
    return ErrorCode::OK;
}
