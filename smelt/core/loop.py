"""Orchestrates Phase 1 (test synthesis) and Phase 2 (generation loop)."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from smelt.config.settings import SmeltConfig
from smelt.core import phase1, phase2

log = logging.getLogger(__name__)


def run(
    spec_path: Path,
    goals_path: Path,
    config: SmeltConfig,
    console: Console,
    module_name: str = "implementation",
    phase1_only: bool = False,
) -> None:
    """Execute a full Smelt run: Phase 1 then Phase 2.

    Args:
        spec_path: Path to the natural language spec file.
        goals_path: Path to the test goals file.
        config: Smelt runtime config.
        console: Rich console for output.
        module_name: Python module name to generate.
        phase1_only: If True, stop after tests are frozen and the manifest is
            written. Does not enter Phase 2.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = config.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    spec = spec_path.read_text(encoding="utf-8")
    goals = goals_path.read_text(encoding="utf-8")

    console.print(f"\n[bold cyan]SMELT[/]  run [dim]{run_id}[/]")
    console.print(f"  spec:    {spec_path}")
    console.print(f"  goals:   {goals_path}")
    console.print(f"  output:  {output_dir}\n")

    # Phase 1
    console.rule("[bold]Phase 1 — Test Synthesis[/]")
    try:
        frozen_test_path = phase1.run(
            spec=spec,
            goals=goals,
            config=config,
            output_dir=output_dir,
            run_id=run_id,
            module_name=module_name,
        )
    except RuntimeError as exc:
        console.print(f"[bold red]Phase 1 FAILED:[/] {exc}")
        _write_trace(output_dir, run_id, "PHASE1_FAILED", [])
        return

    console.print(f"\n  [green]frozen tests:[/] {frozen_test_path}\n")

    if phase1_only:
        _write_trace(output_dir, run_id, "PHASE1_COMPLETE", [])
        console.print("[bold cyan]Phase 1 complete.[/] Tests frozen, manifest written. Stopping before Phase 2.\n")
        console.print("  Resume with:")
        console.print(f"    smelt run --spec {spec_path} --goals {goals_path} --resume {output_dir}\n")
        return

    # Phase 2
    console.rule("[bold]Phase 2 — Generation Loop[/]")
    result = phase2.run(
        spec=spec,
        goals=goals,
        frozen_test_path=frozen_test_path,
        output_dir=output_dir,
        config=config,
        console=console,
        module_name=module_name,
    )

    _write_trace(output_dir, run_id, result.status, result.iterations)

    # Final summary
    console.print()
    if result.status == "CONVERGED":
        console.print(
            f"[bold green]✓ CONVERGED[/]  in {len(result.iterations)} iteration(s)  "
            f"composite={result.final_composite:.2f}"
        )
    else:
        console.print(
            f"[bold yellow]✗ UNCONVERGED[/]  after {len(result.iterations)} iteration(s)  "
            f"final composite={result.final_composite:.2f}"
        )
    console.print(f"  output: {output_dir}\n")


def resume(
    spec_path: Path,
    goals_path: Path,
    config: SmeltConfig,
    console: Console,
    run_dir: Path,
) -> None:
    """Resume a run from a frozen Phase 1 state, skipping Phase 1 entirely.

    Verifies the frozen test file's content hash against manifest.json before
    entering Phase 2. Reuses the same run_id and run directory as the original
    invocation.

    Args:
        spec_path: Path to the natural language spec file (same as original run).
        goals_path: Path to the test goals file (same as original run).
        config: Smelt runtime config.
        console: Rich console for output.
        run_dir: Existing run output directory (e.g. smelt_output/<run_id>) to resume.

    Raises:
        RuntimeError: If run_dir/manifest.json is missing, or the frozen test
            file's content hash does not match the hash recorded in the manifest.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Cannot resume: no manifest.json found in {run_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest["run_id"]
    module_name = manifest["module_name"]
    expected_hash = manifest["test_hash"]

    frozen_dir = run_dir / "frozen_tests"
    ext = ".cpp" if config.language in ("c", "cpp") else ".py"
    frozen_test_path = frozen_dir / f"test_{module_name}{ext}"
    if not frozen_test_path.exists():
        raise RuntimeError(f"Cannot resume: frozen test file not found at {frozen_test_path}")

    actual_hash = hashlib.sha256(frozen_test_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"INTEGRITY VIOLATION: frozen test file {frozen_test_path} does not match "
            f"the hash recorded in {manifest_path}. Aborting resume."
        )

    spec = spec_path.read_text(encoding="utf-8")
    goals = goals_path.read_text(encoding="utf-8")

    console.print(f"\n[bold cyan]SMELT[/]  resuming run [dim]{run_id}[/]")
    console.print(f"  run dir: {run_dir}")
    console.print(f"  frozen tests verified: {frozen_test_path}\n")

    console.rule("[bold]Phase 2 — Generation Loop[/]")
    result = phase2.run(
        spec=spec,
        goals=goals,
        frozen_test_path=frozen_test_path,
        output_dir=run_dir,
        config=config,
        console=console,
        module_name=module_name,
    )

    _write_trace(run_dir, run_id, result.status, result.iterations)

    console.print()
    if result.status == "CONVERGED":
        console.print(
            f"[bold green]✓ CONVERGED[/]  in {len(result.iterations)} iteration(s)  "
            f"composite={result.final_composite:.2f}"
        )
    else:
        console.print(
            f"[bold yellow]✗ UNCONVERGED[/]  after {len(result.iterations)} iteration(s)  "
            f"final composite={result.final_composite:.2f}"
        )
    console.print(f"  output: {run_dir}\n")


def _write_trace(
    output_dir: Path,
    run_id: str,
    status: str,
    iterations: list,
) -> None:
    trace = {
        "run_id": run_id,
        "status": status,
        "iterations": [
            {
                "n": r.n,
                "compliance": r.compliance_score,
                "goal": r.goal_score,
                "composite": r.composite,
            }
            for r in iterations
        ],
    }
    (output_dir / "trace.json").write_text(
        json.dumps(trace, indent=2), encoding="utf-8"
    )
