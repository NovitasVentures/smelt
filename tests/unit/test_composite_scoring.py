"""Tests for CrasisScorer composite scoring: deterministic trigger gate,
deterministic name exemption, learned exemption, and identifier redaction."""

import tomllib
from pathlib import Path

import pytest

from smelt.scorers.crasis_scorer import CrasisScorer, _method_name_from_signature

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


def test_composite_requires_exactly_one_exemption_mechanism():
    always_fires = StubToolkit({"dataflow": {"label": "positive", "confidence": 0.99}})
    both = {
        "violation_specialist": "dataflow",
        "exemption_specialist": "names",
        "exemption_signatures": ["reset_faults"],
    }
    neither = {"violation_specialist": "dataflow"}
    with pytest.raises(ValueError, match="exactly one"):
        _run_composite(always_fires, both, CLEARS_OUTSIDE_RESET)
    with pytest.raises(ValueError, match="exactly one"):
        _run_composite(always_fires, neither, CLEARS_OUTSIDE_RESET)


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
    ("source", "model_consulted"),
    [
        (CLEARS_OUTSIDE_RESET, True),          # member assignment, not exempt
        (CLEARS_INSIDE_RESET, False),          # gated in, but name-exempt before any model call
        (PASS_THROUGH_NO_MEMBER_WRITE, False), # no member write, no clearing-idiom call
        ("void FaultManager::sync_faults() { for (auto& f : faults_) { f = FaultType::NONE; } }", True),
        ("void BatterySupervisor::request_reset() { fault_manager_.reset_faults(); }", True),
        (
            # Pure read loop: comparison only, never assignment.
            "bool FaultManager::has_any_fault() {\n"
            "    for (uint8_t i = 0U; i < CELL_COUNT; ++i) {\n"
            "        if (faults_[i] != FaultType::NONE) { return true; }\n"
            "    }\n"
            "    return false;\n"
            "}",
            False,
        ),
        (
            # Local-only init: assigning NONE to a local is always clean.
            "FaultType FaultManager::get_cell_fault(uint8_t cell) {\n"
            "    FaultType current = FaultType::NONE;\n"
            "    if (cell < CELL_COUNT) { current = faults_[cell]; }\n"
            "    return current;\n"
            "}",
            False,
        ),
    ],
)
def test_profile_trigger_patterns_gate_the_known_shapes(source, model_consulted):
    """The trigger_patterns/exemption_signatures shipped in demo8_bms.toml must
    send every shape that can clear fault state (outside the exempt names) to
    the model, and deterministically exclude read-only/pass-through shapes that
    produced the round-1/round-2 false positives and the exempt reset functions."""
    cfg = _profile_composite_cfg()
    cfg.pop("redact_for_violation", None)
    toolkit = StubToolkit({cfg["violation_specialist"]: {"label": "negative", "confidence": 0.9}})
    _, _ = _run_composite(toolkit, cfg, source)
    assert (len(toolkit.calls) > 0) == model_consulted
