"""Tests for Fix 3: --resume path (smelt.core.loop.resume).

Uses a fabricated run directory (manifest.json + frozen_tests/) and monkeypatches
phase2.run so no LLM calls or real builds happen. Verifies:
- resume() enters Phase 2 in the same run dir (same run_id, writes trace.json there).
- A tampered frozen test file aborts resume with an integrity error before Phase 2 runs.
"""

import hashlib
import json
from pathlib import Path

import pytest
from rich.console import Console

from smelt.config.settings import SmeltConfig
from smelt.core import loop, phase2


def _make_run_dir(tmp_path: Path, test_source: str = "TEST(Suite, Case) { }\n") -> Path:
    run_dir = tmp_path / "smelt_output" / "20260101_000000"
    frozen_dir = run_dir / "frozen_tests"
    frozen_dir.mkdir(parents=True)

    test_file = frozen_dir / "test_bms.cpp"
    test_file.write_text(test_source, encoding="utf-8")

    test_hash = hashlib.sha256(test_source.encode("utf-8")).hexdigest()
    manifest = {
        "run_id": "20260101_000000",
        "spec_hash": "deadbeef",
        "test_hash": test_hash,
        "module_name": "bms",
        "profile": "demo8_bms",
        "language": "cpp",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "mutation_kill_rate": None,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def test_resume_enters_phase2_in_same_run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = _make_run_dir(tmp_path)
    spec_path = tmp_path / "spec.md"
    goals_path = tmp_path / "goals.md"
    spec_path.write_text("spec text", encoding="utf-8")
    goals_path.write_text("goals text", encoding="utf-8")

    captured: dict = {}

    def fake_phase2_run(*, spec, goals, frozen_test_path, output_dir, config, console, module_name):
        captured["output_dir"] = output_dir
        captured["frozen_test_path"] = frozen_test_path
        captured["module_name"] = module_name
        return phase2.LoopResult(status="CONVERGED", iterations=[], final_composite=1.0)

    monkeypatch.setattr(phase2, "run", fake_phase2_run)

    cfg = SmeltConfig(language="cpp")
    loop.resume(
        spec_path=spec_path,
        goals_path=goals_path,
        config=cfg,
        console=Console(),
        run_dir=run_dir,
    )

    assert captured["output_dir"] == run_dir
    assert captured["module_name"] == "bms"
    assert captured["frozen_test_path"] == run_dir / "frozen_tests" / "test_bms.cpp"

    trace = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    assert trace["run_id"] == "20260101_000000"
    assert trace["status"] == "CONVERGED"


def test_resume_aborts_on_tampered_frozen_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = _make_run_dir(tmp_path)
    spec_path = tmp_path / "spec.md"
    goals_path = tmp_path / "goals.md"
    spec_path.write_text("spec text", encoding="utf-8")
    goals_path.write_text("goals text", encoding="utf-8")

    # Tamper with the frozen test after the manifest was written.
    tampered_path = run_dir / "frozen_tests" / "test_bms.cpp"
    tampered_path.write_text("TEST(Suite, Case) { /* tampered */ }\n", encoding="utf-8")

    called = {"phase2_ran": False}

    def fake_phase2_run(**kwargs):
        called["phase2_ran"] = True
        return phase2.LoopResult(status="CONVERGED", iterations=[], final_composite=1.0)

    monkeypatch.setattr(phase2, "run", fake_phase2_run)

    cfg = SmeltConfig(language="cpp")
    with pytest.raises(RuntimeError, match="INTEGRITY VIOLATION"):
        loop.resume(
            spec_path=spec_path,
            goals_path=goals_path,
            config=cfg,
            console=Console(),
            run_dir=run_dir,
        )

    assert called["phase2_ran"] is False
