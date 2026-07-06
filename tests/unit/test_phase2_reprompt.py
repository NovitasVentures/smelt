"""Tests for Phase 2 reprompt continuity: prior-code inclusion and the
always-remind-mandatory-principles-when-passing behavior.

Both were added after Demo 8 BMS run 20260706_004627 showed a real
oscillation: a stateless "regenerate from failure detail alone" reprompt let
the generator silently reintroduce an else-clears violation it had already
fixed, because that iteration's failure list had nothing left to say about
it (see demo/bms/verification/RUN_2026-07-06.md).
"""

from smelt.core.phase2 import _build_prompt, _format_passing_mandatory_reminders
from smelt.scorers.base import ScoreResult, Violation


def test_build_prompt_iteration_one_has_no_prior_code_section():
    prompt = _build_prompt(
        spec="SPEC TEXT",
        goals="GOALS TEXT",
        signatures="TEST(Foo, Bar)",
        n=1,
        prior_scorer_results=None,
        prior_goal=None,
        prior_implementation_source=None,
        weights={},
        scorer_config={},
    )
    assert "YOUR PREVIOUS IMPLEMENTATION" not in prompt
    assert "First attempt" in prompt


def test_build_prompt_includes_prior_implementation_source_verbatim():
    prior_source = "--- FILE: monitoring/fault_manager.cpp ---\nvoid FaultManager::reset_faults() {}\n"
    prompt = _build_prompt(
        spec="SPEC TEXT",
        goals="GOALS TEXT",
        signatures="TEST(Foo, Bar)",
        n=2,
        prior_scorer_results={},
        prior_goal=None,
        prior_implementation_source=prior_source,
        weights={},
        scorer_config={},
    )
    assert "YOUR PREVIOUS IMPLEMENTATION" in prompt
    assert prior_source in prompt
    assert "edit this" in prompt
    assert "do not restart from the spec" in prompt


def test_build_prompt_instructs_keeping_working_code():
    prompt = _build_prompt(
        spec="SPEC TEXT",
        goals="GOALS TEXT",
        signatures="TEST(Foo, Bar)",
        n=2,
        prior_scorer_results={},
        prior_goal=None,
        prior_implementation_source="--- FILE: a.cpp ---\nint x;\n",
        weights={},
        scorer_config={},
    )
    assert "do not rewrite or restructure code" in prompt


def test_passing_mandatory_reminder_excludes_currently_violated_principles():
    scorer_config = {
        "crasis": {
            "mandatory_principles": ["fault-cleared-outside-reset", "platform-dependent-integer-types"],
        },
    }
    # fault-cleared-outside-reset IS currently violated -> excluded from the reminder
    # (it already gets full detail in COMPLIANCE FAILURES elsewhere in the prompt).
    results = {
        "crasis": ScoreResult(
            score=0.5,
            violations=[
                Violation(
                    file="fault_manager.cpp", line=9, rule="ARCH:fault-cleared-outside-reset [mandatory]",
                    message="violates it",
                )
            ],
        )
    }
    reminder = _format_passing_mandatory_reminders(results, scorer_config, {})
    assert "fault-cleared-outside-reset" not in reminder
    assert "platform-dependent-integer-types" in reminder


def test_passing_mandatory_reminder_empty_when_all_mandatory_principles_violated():
    scorer_config = {"crasis": {"mandatory_principles": ["only-rule"]}}
    results = {
        "crasis": ScoreResult(
            score=0.0,
            violations=[Violation(file="x.cpp", line=1, rule="ARCH:only-rule [mandatory]", message="m")],
        )
    }
    reminder = _format_passing_mandatory_reminders(results, scorer_config, {})
    assert reminder == ""


def test_passing_mandatory_reminder_includes_composite_principle_via_violation_specialist_spec():
    scorer_config = {
        "crasis": {
            "mandatory_principles": ["fault-cleared-outside-reset"],
            "composites": {
                "fault-cleared-outside-reset": {"violation_specialist": "fault-clearing-dataflow"},
            },
        },
    }
    crasis_specs = {"fault-clearing-dataflow": {"trigger": "assigns a cleared value to a member"}}
    reminder = _format_passing_mandatory_reminders(None, scorer_config, crasis_specs)
    assert "fault-cleared-outside-reset" in reminder
    assert "assigns a cleared value to a member" in reminder


def test_passing_mandatory_reminder_includes_layer_isolation_when_clean():
    scorer_config = {
        "layer": {"layers": ["hal", "monitoring", "supervision"], "mandatory": True},
    }
    reminder = _format_passing_mandatory_reminders(None, scorer_config, {})
    assert "layer-isolation" in reminder
    assert "hal → monitoring → supervision" in reminder


def test_passing_mandatory_reminder_excludes_layer_isolation_when_violated():
    scorer_config = {
        "layer": {"layers": ["hal", "monitoring"], "mandatory": True},
    }
    results = {
        "layer": ScoreResult(
            score=0.0,
            violations=[Violation(file="x.cpp", line=1, rule="LAYER:layer-isolation [mandatory]", message="m")],
        )
    }
    reminder = _format_passing_mandatory_reminders(results, scorer_config, {})
    assert "layer-isolation" not in reminder


def test_passing_mandatory_reminder_excludes_non_mandatory_layer():
    scorer_config = {
        "layer": {"layers": ["hal", "monitoring"], "mandatory": False},
    }
    reminder = _format_passing_mandatory_reminders(None, scorer_config, {})
    assert reminder == ""


def test_build_prompt_includes_mandatory_reminder_section_when_present():
    scorer_config = {"crasis": {"mandatory_principles": ["some-rule"]}}
    prompt = _build_prompt(
        spec="S", goals="G", signatures="T", n=2,
        prior_scorer_results={}, prior_goal=None,
        prior_implementation_source=None,
        weights={}, scorer_config=scorer_config,
    )
    assert "STILL MANDATORY" in prompt
    assert "some-rule" in prompt


def test_build_prompt_omits_mandatory_reminder_section_when_nothing_to_remind():
    prompt = _build_prompt(
        spec="S", goals="G", signatures="T", n=2,
        prior_scorer_results={}, prior_goal=None,
        prior_implementation_source=None,
        weights={}, scorer_config={},
    )
    assert "STILL MANDATORY" not in prompt
