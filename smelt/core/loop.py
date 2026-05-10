"""Orchestrates Phase 1 (test synthesis) and Phase 2 (generation loop)."""

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
) -> None:
    """Execute a full Smelt run: Phase 1 then Phase 2.

    Args:
        spec_path: Path to the natural language spec file.
        goals_path: Path to the test goals file.
        config: Smelt runtime config.
        console: Rich console for output.
        module_name: Python module name to generate.
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
