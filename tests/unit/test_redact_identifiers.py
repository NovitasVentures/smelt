"""Tests for smelt.scorers.chunker.redact_identifiers."""

from smelt.scorers.chunker import redact_identifiers


def test_redact_identifiers_replaces_class_and_method_qualifier():
    text = "ErrorCode FaultManager::update_cell(uint8_t cell) { return ErrorCode::OK; }"
    result = redact_identifiers(text)
    assert "FaultManager" not in result
    assert "update_cell" not in result
    assert "CLASS_0::FUNC_0(" in result
    # Enum-qualified value must survive untouched.
    assert "ErrorCode::OK" in result


def test_redact_identifiers_replaces_trailing_underscore_members():
    text = "void FaultManager::reset_faults() { faults_[0] = FaultType::NONE; }"
    result = redact_identifiers(text)
    assert "faults_" not in result
    assert "MEMBER_0" in result
    assert "FaultType::NONE" in result


def test_redact_identifiers_preserves_all_caps_constants():
    text = "if (cell >= CELL_COUNT) { return ErrorCode::INVALID_ARGUMENT; }"
    result = redact_identifiers(text)
    assert "CELL_COUNT" in result
    assert "ErrorCode::INVALID_ARGUMENT" in result


def test_redact_identifiers_same_member_maps_to_same_placeholder():
    text = "void FaultManager::reset_faults() { faults_[0] = FaultType::NONE; faults_[1] = FaultType::NONE; }"
    result = redact_identifiers(text)
    assert result.count("MEMBER_0") == 2


def test_redact_identifiers_makes_exempt_and_violating_functions_structurally_identical():
    clean = (
        "void FaultManager::reset_faults() {"
        " for (auto& fault : faults_) { fault = FaultType::NONE; } }"
    )
    violation = (
        "void FaultManager::sync_faults(int32_t voltage_mv) {"
        " for (auto& fault : faults_) { fault = FaultType::NONE; } }"
    )
    redacted_clean = redact_identifiers(clean)
    redacted_violation = redact_identifiers(violation)
    # Both reduce to the same generic shape once the function name is stripped —
    # this is the point: the data-flow specialist cannot and should not try to
    # tell these apart; only the (unredacted) exemption specialist can, via name.
    assert redacted_clean.replace("(int32_t voltage_mv)", "()") == redacted_violation.replace(
        "(int32_t voltage_mv)", "()"
    )


def test_redact_identifiers_replaces_multi_underscore_members():
    text = "fault_manager_.clear_cell_fault_direct(cell);"
    result = redact_identifiers(text)
    assert "fault_manager_" not in result
    assert "MEMBER_" in result


def test_redact_identifiers_preserves_cpp_keywords_and_builtin_types():
    text = "ErrorCode FaultManager::poll(uint8_t cell, int32_t voltage_mv) { if (true) { return ErrorCode::OK; } }"
    result = redact_identifiers(text)
    for keyword in ("if", "true", "return", "uint8_t", "int32_t"):
        assert keyword in result
