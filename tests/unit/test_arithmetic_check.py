"""Tests for smelt.core.arithmetic_check.

Guards against Phase 1's test generator silently baking a wrong expected
value into a frozen test for an integer-arithmetic conversion — a defect
that Phase 2 can never fix (the generator has no write access to frozen
tests), so the run is doomed to UNCONVERGED the moment Phase 1 writes it.
"""

from smelt.core.arithmetic_check import check_test_arithmetic, extract_formulas

BMS_SPEC_EXCERPT = """
- Voltage: `out_mv = (raw_counts * 5000) / 4095` — 12-bit ADC over a 5000 mV reference.
- Temperature: `out_dc = (raw_counts * 1650) / 4095 - 400` — linear sensor spanning
  −40.0 °C to +125.0 °C in deci-degrees.

Calls `poll_cell` for every cell from 0 to `CELL_COUNT - 1` in order.
"""


def test_extract_formulas_finds_conversion_formulas():
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    sources = {f.source for f in formulas}
    assert "out_mv = (raw_counts * 5000) / 4095" in sources
    assert "out_dc = (raw_counts * 1650) / 4095 - 400" in sources


def test_extract_formulas_skips_named_constants():
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    var_names = {f.var_name for f in formulas}
    assert "CELL_COUNT" not in var_names


def test_formula_evaluates_correctly():
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    voltage_formula = next(f for f in formulas if "5000" in f.source)
    assert voltage_formula.evaluate(2048) == 2500
    assert voltage_formula.evaluate(4095) == 5000
    assert voltage_formula.evaluate(0) == 0

    temp_formula = next(f for f in formulas if "1650" in f.source)
    assert temp_formula.evaluate(2048) == 425
    assert temp_formula.evaluate(0) == -400
    assert temp_formula.evaluate(4095) == 1250


def test_check_detects_off_by_one_conversion_bug():
    """The exact bug reproduced 3x this session: raw 3277 -> 4001 mV,
    but a frozen test asserted 4000."""
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    test_source = """
TEST(BatterySupervisor, GetLastVoltage_TwoPolls_ReturnsMostRecent) {
    CellSensor sensor;
    sensor.configure(0, 2867, 2048, true);
    CellMonitor monitor(sensor);
    FaultManager fault_mgr;
    BatterySupervisor supervisor(monitor, fault_mgr);
    supervisor.poll_cell(0);
    sensor.configure(0, 3277, 2048, true);
    supervisor.poll_cell(0);
    int32_t out_mv = 0;
    supervisor.get_last_voltage(0, out_mv);
    EXPECT_EQ(4000, out_mv);
}
"""
    mismatches = check_test_arithmetic(test_source, formulas)

    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.input_value == 3277
    assert m.expected_by_formula == 4001
    assert m.asserted_in_test == 4000


def test_check_passes_clean_correct_test():
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    test_source = """
TEST(CellMonitor, ToMillivolts_Nominal) {
    CellSensor sensor;
    sensor.configure(0, 2048, 0, true);
    CellMonitor monitor(sensor);
    int32_t out_mv = 0;
    monitor.to_millivolts(2048, out_mv);
    EXPECT_EQ(2500, out_mv);
}
"""
    mismatches = check_test_arithmetic(test_source, formulas)
    assert mismatches == []


def test_check_ignores_unrelated_literals_within_tolerance():
    """A literal that happens to be numerically close to a formula's output
    for some configure() value, but is unrelated (e.g. a cell index or error
    code), should not spam unrelated false positives when the input clearly
    isn't feeding that literal."""
    formulas = extract_formulas(BMS_SPEC_EXCERPT)
    test_source = """
TEST(CellSensor, IsReady_OutOfRangeCell_ReturnsFalse) {
    CellSensor sensor;
    sensor.configure(0, 100, 100, true);
    EXPECT_EQ(0, sensor.some_unrelated_field());
}
"""
    # 100 -> voltage formula gives (100*5000)/4095 = 122, far from 0 within
    # tolerance=2, so this must not be flagged.
    mismatches = check_test_arithmetic(test_source, formulas)
    assert mismatches == []


def test_no_formulas_returns_no_mismatches():
    test_source = "TEST(Foo, Bar) { sensor.configure(0, 100, 0, true); EXPECT_EQ(5, x); }"
    assert check_test_arithmetic(test_source, []) == []
