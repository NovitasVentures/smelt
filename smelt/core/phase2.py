"""Phase 2: code generation loop."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text

from smelt.config.settings import SmeltConfig
from smelt.llm import client as llm
from smelt.runners.base import Failure, RunResult
from smelt.runners.pytest_runner import PytestRunner
from smelt.scorers.base import ScoreResult, Violation
from smelt.scorers.ruff_scorer import RuffScorer

log = logging.getLogger(__name__)

_GEN_SYSTEM = """\
You are generating Python code that will be scored and iteratively refined \
against frozen tests.
Do not hardcode values to pass specific tests.
Do not modify test files — they are read-only ground truth.
Fix the failures described. Do not introduce new ones.
Output ONLY the implementation file. No explanation. No markdown fences."""


@dataclass
class IterationRecord:
    """Score record for one iteration."""

    n: int
    compliance_score: float
    goal_score: float
    composite: float


@dataclass
class LoopResult:
    """Final result of the Phase 2 loop."""

    status: str  # "CONVERGED" or "UNCONVERGED"
    iterations: list[IterationRecord] = field(default_factory=list)
    final_composite: float = 0.0


def run(
    spec: str,
    frozen_test_path: Path,
    output_dir: Path,
    config: SmeltConfig,
    console: Console,
    module_name: str = "implementation",
) -> LoopResult:
    """Run the generation loop until convergence or iteration cap.

    Args:
        spec: Original spec text (always included in prompts).
        frozen_test_path: Path to the immutable frozen test file.
        output_dir: Run output directory (contains manifest.json).
        config: Smelt runtime config.
        console: Rich console for terminal output.
        module_name: Python module name to generate (e.g. "implementation").

    Returns:
        LoopResult with status and iteration trace.
    """
    manifest_path = output_dir / "manifest.json"
    test_hash = _sha256(frozen_test_path.read_text(encoding="utf-8"))
    frozen_test_source = frozen_test_path.read_text(encoding="utf-8")

    scorer = RuffScorer()
    runner = PytestRunner()
    records: list[IterationRecord] = []

    prior_compliance: ScoreResult | None = None
    prior_goal: RunResult | None = None
    implementation_source: str = ""

    for n in range(1, config.max_iterations + 1):
        # Integrity check — abort if frozen tests were touched
        _verify_manifest(manifest_path, frozen_test_path, test_hash)

        iter_dir = output_dir / "iterations" / f"{n:03d}"
        code_dir = iter_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)

        # Build prompt
        prompt = _build_prompt(
            spec=spec,
            frozen_test_source=frozen_test_source,
            n=n,
            prior_compliance=prior_compliance,
            prior_goal=prior_goal,
        )

        log.info("Phase 2 iteration %d: generating implementation", n)
        implementation_source = llm.complete(
            system=_GEN_SYSTEM,
            user=prompt,
            model=config.model,
            max_tokens=config.max_tokens,
        )

        impl_file = code_dir / f"{module_name}.py"
        impl_file.write_text(implementation_source, encoding="utf-8")

        # Score
        compliance_result = scorer.score(code_dir, config={})
        goal_result = runner.run(frozen_test_path, code_dir, config={})
        composite = compliance_result.score * goal_result.goal_score

        # Write iteration artifacts
        _write_iteration(iter_dir, compliance_result, goal_result, n, composite)

        record = IterationRecord(
            n=n,
            compliance_score=compliance_result.score,
            goal_score=goal_result.goal_score,
            composite=composite,
        )
        records.append(record)

        # Render
        _render(console, record, compliance_result.violations, goal_result.failures, config)

        prior_compliance = compliance_result
        prior_goal = goal_result

        if (
            compliance_result.score >= config.compliance_threshold
            and goal_result.goal_score >= config.goal_threshold
        ):
            _write_final(output_dir, code_dir, module_name, implementation_source)
            return LoopResult(status="CONVERGED", iterations=records, final_composite=composite)

    _write_final(output_dir, code_dir, module_name, implementation_source)
    return LoopResult(status="UNCONVERGED", iterations=records, final_composite=records[-1].composite if records else 0.0)


def _verify_manifest(manifest_path: Path, frozen_test_path: Path, original_hash: str) -> None:
    """Abort if the frozen test file has been modified."""
    current_hash = _sha256(frozen_test_path.read_text(encoding="utf-8"))
    if current_hash != original_hash:
        raise RuntimeError(
            f"INTEGRITY VIOLATION: frozen test file {frozen_test_path} has been modified. "
            "Aborting run."
        )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("test_hash") != original_hash:
            raise RuntimeError(
                "INTEGRITY VIOLATION: manifest test_hash does not match frozen test file. "
                "Aborting run."
            )


def _build_prompt(
    spec: str,
    frozen_test_source: str,
    n: int,
    prior_compliance: ScoreResult | None,
    prior_goal: RunResult | None,
) -> str:
    if n == 1:
        return (
            f"SPEC:\n{spec}\n\n"
            f"FROZEN TESTS (read-only reference):\n{frozen_test_source}\n\n"
            "Generate the implementation."
        )

    compliance_section = _format_compliance_failures(prior_compliance)
    goal_section = _format_goal_failures(prior_goal)
    composite = (prior_compliance.score if prior_compliance else 0.0) * (
        prior_goal.goal_score if prior_goal else 0.0
    )

    return (
        f"SPEC:\n{spec}\n\n"
        f"ITERATION: {n} | SCORE: {composite:.2f}  "
        f"compliance={prior_compliance.score:.2f}  "
        f"goal={prior_goal.goal_score:.2f}\n\n"
        f"COMPLIANCE FAILURES ({len(prior_compliance.violations) if prior_compliance else 0}):\n"
        f"{compliance_section}\n\n"
        f"TEST FAILURES ({prior_goal.failed if prior_goal else 0}):\n"
        f"{goal_section}\n\n"
        "Fix the implementation. Return ONLY the corrected file."
    )


def _format_compliance_failures(result: ScoreResult | None) -> str:
    if not result or not result.violations:
        return "  (none)"
    lines = [f"  {v.rule}  line {v.line}  {v.message}" for v in result.violations[:20]]
    if len(result.violations) > 20:
        lines.append(f"  ... and {len(result.violations) - 20} more")
    return "\n".join(lines)


def _format_goal_failures(result: RunResult | None) -> str:
    if not result or not result.failures:
        return "  (none)"
    parts = []
    for f in result.failures[:10]:
        parts.append(f"  {f.test_name}\n    {f.message[:200]}")
    return "\n".join(parts)


def _write_iteration(
    iter_dir: Path,
    compliance: ScoreResult,
    goal: RunResult,
    n: int,
    composite: float,
) -> None:
    (iter_dir / "compliance.json").write_text(
        json.dumps(
            {
                "score": compliance.score,
                "violations": [
                    {"file": v.file, "line": v.line, "rule": v.rule, "message": v.message}
                    for v in compliance.violations
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (iter_dir / "goal.json").write_text(
        json.dumps(
            {
                "passed": goal.passed,
                "failed": goal.failed,
                "goal_score": goal.goal_score,
                "failures": [
                    {"test_name": f.test_name, "message": f.message}
                    for f in goal.failures
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (iter_dir / "score.json").write_text(
        json.dumps(
            {
                "iteration": n,
                "compliance_score": compliance.score,
                "goal_score": goal.goal_score,
                "composite": composite,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_final(
    output_dir: Path, code_dir: Path, module_name: str, source: str
) -> None:
    final_dir = output_dir / "final" / "code"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _render(
    console: Console,
    record: IterationRecord,
    violations: list[Violation],
    failures: list[Failure],
    config: SmeltConfig,
) -> None:
    def bar(score: float, width: int = 10) -> str:
        filled = round(score * width)
        return "█" * filled + "░" * (width - filled)

    lines: list[str] = [
        f"  compliance   {bar(record.compliance_score)}  {record.compliance_score:.2f}",
        f"  goal         {bar(record.goal_score)}  {record.goal_score:.2f}",
        f"  composite    {bar(record.composite)}  {record.composite:.2f}",
    ]

    if violations:
        lines.append(f"\n  compliance failures: {len(violations)}")
        for v in violations[:5]:
            lines.append(f"    {v.rule}  line {v.line}  {v.message[:60]}")
        if len(violations) > 5:
            lines.append(f"    ... and {len(violations) - 5} more")

    if failures:
        lines.append(f"\n  test failures: {len(failures)}")
        for f in failures[:5]:
            lines.append(f"    {f.test_name.split('::')[-1]} FAILED")
        if len(failures) > 5:
            lines.append(f"    ... and {len(failures) - 5} more")

    converged = (
        record.compliance_score >= config.compliance_threshold
        and record.goal_score >= config.goal_threshold
    )

    if converged:
        title = f"[bold green]✓ CONVERGED[/]  iteration {record.n}/{config.max_iterations}"
    else:
        title = f"[bold cyan]SMELT[/]  iteration {record.n}/{config.max_iterations}"

    console.print(
        Panel("\n".join(lines), title=title, border_style="bright_blue")
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
