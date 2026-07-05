// Real generated shape (2026-07-05 run 20260705_205805, iteration 14):
// pure assignment via std::array::at(), zero comparison operators against
// the raw-flavored parameters. Confirmed by direct classify() to score
// 0.9476 positive pre-gate (vs 0.7081 for the [] -indexed variant already
// in this suite) -- the model keys on surface "raw identifier near array
// indexing", not the comparison the rule actually requires. Gated out by
// trigger_patterns before this ever reaches the model.
auto CellSensor::configure(uint8_t cell, int32_t raw_voltage, int32_t raw_temp, bool ready) -> void {
    if (cell >= CELL_COUNT) {
        return;
    }
    raw_voltage_.at(cell) = raw_voltage;
    raw_temp_.at(cell) = raw_temp;
    ready_.at(cell) = ready;
}
