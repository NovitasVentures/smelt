"""Tests for CrasisScorer composite scoring: deterministic trigger gate,
deterministic name exemption, learned exemption, and identifier redaction."""

import tomllib
from pathlib import Path

import pytest

from smelt.scorers.crasis_scorer import (
    CrasisScorer,
    _cleared_value_assignment_verdict,
    _delegation_call_verdict,
    _method_name_from_signature,
)

PROFILE_PATH = Path(__file__).resolve().parents[2] / "smelt" / "config" / "profiles" / "demo8_bms.toml"

CLEARS_OUTSIDE_RESET = """\
ErrorCode FaultManager::update_cell(uint8_t cell, int32_t voltage_mv) {
    if (voltage_mv > OVER_VOLTAGE_MV) {
        faults_[cell] = FaultType::OVER_VOLTAGE;
    } else {
        faults_[cell] = FaultType::NONE;
    }
    return ErrorCode::OK;
}
"""

CLEARS_INSIDE_RESET = """\
void FaultManager::reset_faults() {
    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {
        faults_[i] = FaultType::NONE;
    }
}
"""

PASS_THROUGH_NO_MEMBER_WRITE = """\
ErrorCode CellMonitor::read_cell_voltage(uint8_t cell, int32_t& out_mv) {
    if (cell >= CELL_COUNT) {
        return ErrorCode::INVALID_ARGUMENT;
    }
    int32_t raw_counts = 0;
    ErrorCode status = sensor_.read_voltage_raw(cell, raw_counts);
    if (status != ErrorCode::OK) {
        return status;
    }
    return to_millivolts(raw_counts, out_mv);
}
"""


class StubToolkit:
    """Duck-typed CrasisToolkit: canned answers per specialist, records calls."""

    def __init__(self, answers: dict[str, dict]):
        self._answers = answers
        self.calls: list[tuple[str, str]] = []

    def classify(self, specialist: str, text: str) -> dict:
        self.calls.append((specialist, text))
        return self._answers[specialist]


def _run_composite(toolkit, composite_cfg, source):
    scorer = CrasisScorer()
    return scorer._score_composite(
        toolkit=toolkit,
        composite_cfg=composite_cfg,
        principle_name="fault-cleared-outside-reset",
        specialist_meta={},
        source=source,
        src_file=Path("monitoring/fault_manager.cpp"),
        is_cpp=True,
        is_mandatory=True,
        per_specialist_thresholds={},
        default_threshold=0.85,
    )


def _profile_composite_cfg() -> dict:
    with PROFILE_PATH.open("rb") as fh:
        profile = tomllib.load(fh)
    return profile["scorers"]["crasis"]["composites"]["fault-cleared-outside-reset"]


def test_composite_rejects_both_exemption_mechanisms_at_once():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    both = {
        "violation_specialist": "dataflow",
        "exemption_specialist": "names",
        "exemption_signatures": ["reset_faults"],
    }
    with pytest.raises(ValueError, match="at most one"):
        _run_composite(always_fires, both, CLEARS_OUTSIDE_RESET)


def test_composite_rejects_no_gate_or_exemption_mechanism_at_all():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    nothing_configured = {"violation_specialist": "dataflow"}
    with pytest.raises(ValueError, match="at least one"):
        _run_composite(always_fires, nothing_configured, CLEARS_OUTSIDE_RESET)


def test_composite_trigger_gate_alone_is_a_valid_configuration():
    """A rule with no separate 'is this permitted' question — the gated model
    verdict is final — needs no exemption tier at all, only a trigger gate."""
    fires_on_comparison = StubToolkit({"raw_check": {"label": "positive", "confidence": 0.95}})
    cfg = {
        "violation_specialist": "raw_check",
        "trigger_patterns": [r"\braw_\w*\s*(?:>=|<=|==|!=|>|<)"],
    }
    assignment_only = "void CellSensor::configure(int32_t raw_voltage) { raw_voltage_ = raw_voltage; }"
    comparison_present = "void FaultManager::update_cell(int32_t raw_counts) { if (raw_counts > 3440) {} }"

    violations, _ = _run_composite(fires_on_comparison, cfg, assignment_only)
    assert violations == []
    assert fires_on_comparison.calls == []

    violations, _ = _run_composite(fires_on_comparison, cfg, comparison_present)
    assert len(violations) == 1
    assert "no name exemption" not in violations[0].message


def test_signature_exemption_suppresses_violation_without_model_call():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults", "clear_faults"],
    }
    violations, n_chunks = _run_composite(always_fires, cfg, CLEARS_INSIDE_RESET)
    assert violations == []
    assert n_chunks == 1
    # Exemption is decided from the signature — the model is never consulted.
    assert always_fires.calls == []


def test_non_exempt_name_fires_with_name_exemption_detail():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults", "clear_faults"],
    }
    violations, _ = _run_composite(always_fires, cfg, CLEARS_OUTSIDE_RESET)
    assert len(violations) == 1
    assert violations[0].rule == "ARCH:fault-cleared-outside-reset [mandatory]"
    assert "no name exemption" in violations[0].message
    assert "update_cell" in violations[0].message


def test_trigger_gate_skips_chunk_without_model_call():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults"],
        # Gate requires an assignment to a trailing-underscore member.
        "trigger_patterns": [r"\b\w+_\s*(?:\[[^\]]*\]\s*)?(?:[&|^]?=)(?!=)"],
    }
    violations, n_chunks = _run_composite(always_fires, cfg, PASS_THROUGH_NO_MEMBER_WRITE)
    assert violations == []
    assert n_chunks == 1
    assert always_fires.calls == []


def test_learned_exemption_specialist_still_supported():
    exempt = StubToolkit({
        "dataflow": {"label": "positive", "confidence": 0.99},
        "names": {"label": "positive", "confidence": 0.95},
    })
    not_exempt = StubToolkit({
        "dataflow": {"label": "positive", "confidence": 0.99},
        "names": {"label": "negative", "confidence": 0.95},
    })
    cfg = {"violation_specialist": "dataflow", "exemption_specialist": "names"}
    violations, _ = _run_composite(exempt, cfg, CLEARS_OUTSIDE_RESET)
    assert violations == []
    violations, _ = _run_composite(not_exempt, cfg, CLEARS_OUTSIDE_RESET)
    assert len(violations) == 1
    assert "exemption=95%" in violations[0].message


def test_redact_for_violation_classifies_redacted_text():
    toolkit = StubToolkit({"dataflow": {"label": "negative", "confidence": 0.9}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults"],
        "redact_for_violation": True,
    }
    _run_composite(toolkit, cfg, CLEARS_OUTSIDE_RESET)
    assert len(toolkit.calls) == 1
    _, classified_text = toolkit.calls[0]
    assert "faults_" not in classified_text
    assert "update_cell" not in classified_text
    assert "FaultType::NONE" in classified_text


def test_redaction_preserve_prefixes_reach_the_classifier_text():
    reinit_before_evaluate = (
        "ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {\n"
        "    fault_manager_.reset_faults();\n"
        "    fault_manager_.update_cell(cell, 0, 0);\n"
        "    return ErrorCode::OK;\n"
        "}\n"
    )
    toolkit = StubToolkit({"dataflow": {"label": "negative", "confidence": 0.9}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults", "clear_faults"],
        "redact_for_violation": True,
        "redaction_preserve_prefixes": ["reset", "clear"],
    }
    _run_composite(toolkit, cfg, reinit_before_evaluate)
    assert len(toolkit.calls) == 1
    _, classified_text = toolkit.calls[0]
    assert "reset_faults(" in classified_text
    assert "update_cell" not in classified_text
    assert "poll_cell" not in classified_text


def test_below_threshold_violation_does_not_fire():
    weak = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.60}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults"],
    }
    violations, _ = _run_composite(weak, cfg, CLEARS_OUTSIDE_RESET)
    assert violations == []


@pytest.mark.parametrize(
    ("signature", "expected"),
    [
        ("void FaultManager::reset_faults()", "reset_faults"),
        ("ErrorCode CellMonitor::read_cell_voltage(uint8_t cell, int32_t& out_mv)", "read_cell_voltage"),
        ("auto BatterySupervisor::poll_cell(uint8_t cell) -> ErrorCode", "poll_cell"),
        ("bool FaultManager::has_any_fault() const", "has_any_fault"),
        ("FaultManager.update_cell", "update_cell"),
        ("standalone_function", "standalone_function"),
    ],
)
def test_method_name_from_signature(signature, expected):
    assert _method_name_from_signature(signature) == expected


@pytest.mark.parametrize(
    ("source", "expected_violation", "model_should_be_consulted"),
    [
        (CLEARS_OUTSIDE_RESET, True, False),          # cleared-value member assignment: deterministic
        (CLEARS_INSIDE_RESET, False, False),          # name-exempt before any deterministic check or model call
        (PASS_THROUGH_NO_MEMBER_WRITE, False, False), # gated out: no cleared-value literal, no clearing call
        (
            # Range-based loop clearing a member OUTSIDE a reset-named function: violation.
            "void FaultManager::sync_faults() { for (auto& f : faults_) { f = FaultType::NONE; } }",
            True, False,
        ),
        (
            # Pure delegation wrapper: the reset call IS the body. Clean.
            "void BatterySupervisor::request_reset() { fault_manager_.reset_faults(); }",
            False, False,
        ),
        (
            # Reinit-before-evaluate: a reset call followed by further work. Violation.
            # The ONLY textual difference from the clean poll_cell shape below is this call.
            "ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {\n"
            "    int32_t voltage_mv = 0;\n"
            "    fault_manager_.reset_faults();\n"
            "    fault_manager_.update_cell(cell, voltage_mv, 0);\n"
            "    last_mv_[cell] = voltage_mv;\n"
            "    return ErrorCode::OK;\n"
            "}",
            True, False,
        ),
        (
            # The 2026-07-05 neg__poll_cell false positive: same shape as above minus
            # the reset call. No cleared-value assignment, no clearing call -> gated out.
            "ErrorCode BatterySupervisor::poll_cell(uint8_t cell) {\n"
            "    int32_t voltage_mv = 0;\n"
            "    fault_manager_.update_cell(cell, voltage_mv, 0);\n"
            "    last_mv_[cell] = voltage_mv;\n"
            "    return ErrorCode::OK;\n"
            "}",
            False, False,
        ),
        (
            # Pure read loop: comparison only, never assignment.
            "bool FaultManager::has_any_fault() {\n"
            "    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {\n"
            "        if (faults_[i] != FaultType::NONE) { return true; }\n"
            "    }\n"
            "    return false;\n"
            "}",
            False, False,
        ),
        (
            # The 2026-07-05 neg__shape3_query_local_init false positive: local variable
            # assigned NONE, never a member -> deterministically clean, no model call.
            "FaultType FaultManager::get_cell_fault(uint8_t cell) {\n"
            "    FaultType current = FaultType::NONE;\n"
            "    if (cell < CELL_COUNT) { current = faults_[cell]; }\n"
            "    return current;\n"
            "}",
            False, False,
        ),
    ],
)
def test_profile_composite_resolves_the_known_shapes_deterministically(
    source, expected_violation, model_should_be_consulted
):
    """The full deterministic stack shipped in demo8_bms.toml (exemption
    signatures, trigger gate, delegation-call verdict, cleared-value verdict)
    must resolve every known shape — including both false positives found on
    real generated code in run 20260705_205805 — WITHOUT consulting the model.
    A toolkit that always answers wrong (negative when a violation is
    expected, or vice versa) is used so any accidental fallthrough to the
    model would flip the verdict and fail the test."""
    cfg = _profile_composite_cfg()
    cfg.pop("redact_for_violation", None)
    wrong_answer = "negative" if expected_violation else "positive"
    toolkit = StubToolkit({cfg["violation_specialist"]: {"label": wrong_answer, "confidence": 0.99}})
    violations, _ = _run_composite(toolkit, cfg, source)
    assert bool(violations) == expected_violation
    assert (len(toolkit.calls) > 0) == model_should_be_consulted


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("void CLASS_0::FUNC_0() { MEMBER_0.reset_faults(); }", False),  # pure delegation
        (
            "void CLASS_0::FUNC_0() { if (!MEMBER_1) { return; } MEMBER_0.clear_faults(); }",
            False,  # guard clause + delegation only
        ),
        (
            "ErrorCode CLASS_0::FUNC_0() { MEMBER_0.reset_faults(); return ErrorCode::OK; }",
            False,  # delegation + bare trailing return
        ),
        (
            "ErrorCode CLASS_0::FUNC_0(uint8_t cell) {\n"
            "    MEMBER_1.reset_faults();\n"
            "    MEMBER_1.update_cell(cell, 0, 0);\n"
            "    return ErrorCode::OK;\n"
            "}",
            True,  # reset call followed by further work: reinit-before-evaluate
        ),
    ],
)
def test_delegation_call_verdict_distinguishes_pure_delegation_from_reinit(text, expected):
    patterns = [__import__("re").compile(r"\b(?:\w+_\s*\.\s*)?(?:reset|clear)\w*\s*\([^)]*\)\s*;")]
    assert _delegation_call_verdict(text, patterns) is expected


def test_delegation_call_verdict_returns_none_when_no_pattern_matches():
    patterns = [__import__("re").compile(r"\b(?:\w+_\s*\.\s*)?(?:reset|clear)\w*\s*\([^)]*\)\s*;")]
    no_clearing_call = "void CLASS_0::FUNC_0() { MEMBER_0.update_cell(0, 0, 0); }"
    assert _delegation_call_verdict(no_clearing_call, patterns) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # This deterministic tier runs on the ORIGINAL (unredacted) chunk text —
        # crasis_scorer.py calls it as `_cleared_value_assignment_verdict(chunk.text, ...)`,
        # before the separate redact_for_violation step that only applies to the
        # model fallback path — so it sees real trailing-underscore member names,
        # never the MEMBER_n placeholders redact_identifiers() would produce.
        ("faults_[cell] = FaultType::NONE;", True),                      # indexed member assignment
        ("faults_ = FaultType::NONE;", True),                            # bare member assignment
        (
            "for (auto& fault : faults_) { fault = FaultType::NONE; }",
            True,  # range-based loop over a member container
        ),
        ("FaultType current = FaultType::NONE;", False),                 # local variable, not a member
        ("if (faults_[cell] != FaultType::NONE) { return true; }", False),  # comparison, not assignment
        ("faults_[cell] = FaultType::OVER_VOLTAGE;", False),              # different value entirely
    ],
)
def test_cleared_value_assignment_verdict(text, expected):
    assert _cleared_value_assignment_verdict(text, ["FaultType::NONE"]) is expected


LAUNDERED_ELSE_CLEAR = """\
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
"""


def test_cleared_value_assignment_verdict_detects_laundering_through_a_local():
    """A local variable initialized to the cleared value and later assigned
    into a member is a real violation (semantically identical to an
    else-clear) that pure literal-adjacency matching cannot resolve on its
    own — it must return None (defer to the model), not False (clean).
    Confirmed against a real generated example, 2026-07-05 run
    20260705_215725 iteration 12: this exact shape scored 99.6% positive
    when the trained specialist was actually consulted."""
    assert _cleared_value_assignment_verdict(LAUNDERED_ELSE_CLEAR, ["FaultType::NONE"]) is None


def test_composite_falls_through_to_model_for_laundered_else_clear():
    """End-to-end: the composite must consult the model (not silently pass)
    for the laundering shape, and must actually raise the violation when the
    model correctly classifies it positive — this is the real regression
    this test guards against: an earlier version of _score_composite treated
    ANY False/no-direct-match cleared-value result as authoritative and
    never called the model at all for this shape, silently missing a real
    architectural violation."""
    toolkit = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.996}})
    cfg = {
        "violation_specialist": "dataflow",
        "exemption_signatures": ["reset_faults", "clear_faults"],
        "trigger_patterns": ["FaultType::NONE"],
        "cleared_value_patterns": ["FaultType::NONE"],
    }
    violations, _ = _run_composite(toolkit, cfg, LAUNDERED_ELSE_CLEAR)
    assert len(toolkit.calls) == 1
    assert len(violations) == 1
