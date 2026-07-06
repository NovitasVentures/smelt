// VIOLATION (shape 12, found on real generated code 2026-07-06 run
// 20260706_021845 iteration 3 -- the run's compliance score falsely
// reached CONVERGED with this exact violation present, undetected).
// Textually identical to shape5's else-clears except std::array::at(cell)
// bounds-checked indexing is used instead of faults_[cell] -- the two
// forms are semantically identical member access, but the deterministic
// cleared-value check's regex only recognized [] indexing until this fix,
// silently missing every .at()-indexed else-clear (an idiomatic, common
// C++ style this generator uses constantly).
auto FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) -> ErrorCode {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_.at(cell) = FaultType::OVER_VOLTAGE;
    } else if (voltage_mv < UNDER_VOLTAGE_MV) {
        faults_.at(cell) = FaultType::UNDER_VOLTAGE;
    } else if (temp_dc > OVER_TEMP_DC) {
        faults_.at(cell) = FaultType::OVER_TEMP;
    } else {
        faults_.at(cell) = FaultType::NONE;
    }
    return ErrorCode::OK;
}
