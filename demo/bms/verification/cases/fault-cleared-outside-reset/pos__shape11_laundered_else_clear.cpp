// VIOLATION (shape 11, found on real generated code 2026-07-05 run
// 20260705_215725 iteration 12): semantically identical to shape5's
// else-clears, but the cleared value is routed through a local variable
// first, dodging a literal "MEMBER = FaultType::NONE" text match. faults_
// is unconditionally overwritten with `fault`, which still holds
// FaultType::NONE whenever no branch above fired -- an in-range poll after
// a latched fault silently un-latches it, identical to the original bug.
auto FaultManager::update_cell(uint8_t cell, int32_t voltage_mv, int32_t temp_dc) -> ErrorCode {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    FaultType fault = FaultType::NONE;
    if (voltage_mv > OVER_VOLTAGE_MV) {
        fault = FaultType::OVER_VOLTAGE;
    } else if (voltage_mv < UNDER_VOLTAGE_MV) {
        fault = FaultType::UNDER_VOLTAGE;
    } else if (temp_dc > OVER_TEMP_DC) {
        fault = FaultType::OVER_TEMP;
    }
    faults_.at(cell) = fault;
    return ErrorCode::OK;
}
