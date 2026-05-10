"""Phase 2: code generation loop."""

import ast
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from smelt.config.settings import SmeltConfig
from smelt.llm import client as llm
from smelt.runners.base import Failure, RunResult
from smelt.runners.pytest_runner import PytestRunner
from smelt.scorers.base import ScoreResult, Violation

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
    scorer_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class LoopResult:
    """Final result of the Phase 2 loop."""

    status: str  # "CONVERGED" or "UNCONVERGED"
    iterations: list[IterationRecord] = field(default_factory=list)
    final_composite: float = 0.0


def extract_signatures(test_file: Path) -> str:
    """Extract test function signatures from a frozen test file.

    Args:
        test_file: Path to the frozen test file.

    Returns:
        Newline-joined list of test function signatures (name + params, no body).
    """
    source = test_file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    signatures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        args = node.args
        params: list[str] = []
        # positional args
        for arg in args.args:
            params.append(arg.arg)
        # *args
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        # keyword-only args
        for arg in args.kwonlyargs:
            params.append(arg.arg)
        # **kwargs
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        signatures.append(f"{node.name}({', '.join(params)})")

    return "\n".join(signatures)


def _assert_no_test_source(prompt: str, frozen_test_path: Path) -> None:
    """Hard guarantee that test source never reaches the generation prompt."""
    test_source = frozen_test_path.read_text()
    words = test_source.split()
    for i in range(len(words) - 9):
        window = " ".join(words[i : i + 10])
        if window in prompt:
            raise RuntimeError(
                f"Test source detected in generation prompt. "
                f"Matched: '{window[:60]}...'\n"
                f"This violates CLAUDE.md Non-Negotiable Rule 7."
            )


def run(
    spec: str,
    goals: str,
    frozen_test_path: Path,
    output_dir: Path,
    config: SmeltConfig,
    console: Console,
    module_name: str = "implementation",
) -> LoopResult:
    """Run the generation loop until convergence or iteration cap.

    Args:
        spec: Original spec text (always included in prompts).
        goals: Original test goals text (always included in prompts).
        frozen_test_path: Path to the immutable frozen test file.
        output_dir: Run output directory (contains manifest.json).
        config: Smelt runtime config.
        console: Rich console for terminal output.
        module_name: Python module name to generate (e.g. "implementation").

    Returns:
        LoopResult with status and iteration trace.
    """
    from smelt.scorers import SCORER_REGISTRY

    manifest_path = output_dir / "manifest.json"
    test_hash = _sha256(frozen_test_path.read_text(encoding="utf-8"))
    signatures = extract_signatures(frozen_test_path)

    scorers = {name: SCORER_REGISTRY[name]() for name in config.scorers if name in SCORER_REGISTRY}
    runner = PytestRunner()
    records: list[IterationRecord] = []

    prior_scorer_results: dict[str, ScoreResult] | None = None
    prior_goal: RunResult | None = None

    for n in range(1, config.max_iterations + 1):
        # Integrity check — abort if frozen tests were touched
        _verify_manifest(manifest_path, frozen_test_path, test_hash)

        iter_dir = output_dir / "iterations" / f"{n:03d}"
        code_dir = iter_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)

        prompt = _build_prompt(
            spec=spec,
            goals=goals,
            signatures=signatures,
            n=n,
            prior_scorer_results=prior_scorer_results,
            prior_goal=prior_goal,
            weights=config.scorer_weights,
        )

        # Hard abort if test source leaked into prompt
        _assert_no_test_source(prompt, frozen_test_path)

        log.info("Phase 2 iteration %d: generating implementation", n)
        implementation_source = llm.complete(
            system=_GEN_SYSTEM,
            user=prompt,
            model=config.model,
            max_tokens=config.max_tokens,
        )

        impl_file = code_dir / f"{module_name}.py"
        impl_file.write_text(implementation_source, encoding="utf-8")

        scorer_results: dict[str, ScoreResult] = {}
        for name, scorer in scorers.items():
            scorer_results[name] = scorer.score(code_dir, config=config.scorer_config.get(name, {}))

        compliance_score = _weighted_compliance(scorer_results, config.scorer_weights)
        goal_result = runner.run(frozen_test_path, code_dir, config={})
        composite = compliance_score * goal_result.goal_score

        _write_iteration(iter_dir, scorer_results, goal_result, n, compliance_score, composite)

        record = IterationRecord(
            n=n,
            compliance_score=compliance_score,
            goal_score=goal_result.goal_score,
            composite=composite,
            scorer_scores={name: r.score for name, r in scorer_results.items()},
        )
        records.append(record)

        _render(console, record, scorer_results, goal_result, config)

        prior_scorer_results = scorer_results
        prior_goal = goal_result

        if (
            compliance_score >= config.compliance_threshold
            and goal_result.goal_score >= config.goal_threshold
        ):
            _write_final(output_dir, code_dir, module_name, implementation_source)
            return LoopResult(status="CONVERGED", iterations=records, final_composite=composite)

    _write_final(output_dir, code_dir, module_name, implementation_source)
    return LoopResult(
        status="UNCONVERGED",
        iterations=records,
        final_composite=records[-1].composite if records else 0.0,
    )


def _weighted_compliance(results: dict[str, ScoreResult], weights: dict[str, float]) -> float:
    """Compute weighted mean compliance score across all scorers."""
    if not results:
        return 1.0
    if not weights:
        return sum(r.score for r in results.values()) / len(results)
    total_weight = sum(weights.get(name, 1.0) for name in results)
    return sum(results[name].score * weights.get(name, 1.0) for name in results) / total_weight


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
    goals: str,
    signatures: str,
    n: int,
    prior_scorer_results: dict[str, ScoreResult] | None,
    prior_goal: RunResult | None,
    weights: dict[str, float],
) -> str:
    header = (
        f"SPEC:\n{spec}\n\n"
        f"TEST GOALS (what the tests verify — not the test code):\n{goals}\n\n"
        f"TEST FUNCTION SIGNATURES (names only — you cannot see the assertions):\n{signatures}\n\n"
        f"ITERATION: {n}\n"
    )

    if n == 1:
        return header + "First attempt — implement from spec and goals."

    compliance_score = _weighted_compliance(prior_scorer_results or {}, weights)
    goal_score = prior_goal.goal_score if prior_goal else 0.0
    composite = compliance_score * goal_score

    compliance_section = _format_compliance_failures(prior_scorer_results)
    goal_section = _format_goal_failures(prior_goal)

    return (
        header
        + f"SCORE: {composite:.2f}  compliance={compliance_score:.2f}  goal={goal_score:.2f}\n\n"
        f"COMPLIANCE FAILURES:\n{compliance_section}\n\n"
        f"TEST FAILURES ({prior_goal.failed if prior_goal else 0}):\n{goal_section}\n\n"
        "Fix the implementation. Return ONLY the corrected file."
    )


def _format_compliance_failures(results: dict[str, ScoreResult] | None) -> str:
    if not results:
        return "  (none)"
    lines: list[str] = []
    for scorer_name, result in results.items():
        for v in result.violations[:20]:
            lines.append(f"  {scorer_name}  {v.rule}  line {v.line}  {v.message}")
    if not lines:
        return "  (none)"
    total = sum(len(r.violations) for r in results.values())
    if total > 20:
        lines.append(f"  ... and {total - 20} more")
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
    scorer_results: dict[str, ScoreResult],
    goal: RunResult,
    n: int,
    compliance_score: float,
    composite: float,
) -> None:
    all_violations = []
    scorer_scores = {}
    for name, result in scorer_results.items():
        scorer_scores[name] = result.score
        for v in result.violations:
            all_violations.append(
                {"scorer": name, "file": v.file, "line": v.line, "rule": v.rule, "message": v.message}
            )

    (iter_dir / "compliance.json").write_text(
        json.dumps(
            {
                "score": compliance_score,
                "scorer_scores": scorer_scores,
                "violations": all_violations,
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
                "compliance_score": compliance_score,
                "scorer_scores": scorer_scores,
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
    scorer_results: dict[str, ScoreResult],
    goal_result: RunResult,
    config: SmeltConfig,
) -> None:
    def bar(score: float, width: int = 10) -> str:
        filled = round(score * width)
        return "█" * filled + "░" * (width - filled)

    total_tests = goal_result.passed + goal_result.failed
    lines: list[str] = [f"  iteration {record.n}/{config.max_iterations}", ""]

    # Per-scorer compliance rows
    lines.append("  compliance")
    for name, result in scorer_results.items():
        vcount = len(result.violations)
        suffix = f"  {vcount} violation{'s' if vcount != 1 else ''}" if vcount else ""
        lines.append(f"    {name:<8}  {bar(result.score)}  {result.score:.2f}{suffix}")
    lines.append(
        f"    {'weighted':<8}  {bar(record.compliance_score)}  {record.compliance_score:.2f}"
    )

    # Goal row
    lines.append("")
    passing_str = f"  {goal_result.passed}/{total_tests} tests passing" if total_tests else ""
    lines.append(f"  goal      {bar(record.goal_score)}  {record.goal_score:.2f}{passing_str}")

    # Composite
    lines.append(f"\n  composite {bar(record.composite)}  {record.composite:.2f}")

    # Compliance failure detail
    all_violations: list[tuple[str, Violation]] = []
    for name, result in scorer_results.items():
        for v in result.violations[:5]:
            all_violations.append((name, v))
    if all_violations:
        lines.append("\n  compliance failures:")
        for name, v in all_violations[:8]:
            lines.append(f"    {name}  {v.rule}  line {v.line}  {v.message[:60]}")
        total_v = sum(len(r.violations) for r in scorer_results.values())
        if total_v > 8:
            lines.append(f"    ... and {total_v - 8} more")

    # Test failure detail
    if goal_result.failures:
        lines.append("\n  test failures:")
        for f in goal_result.failures[:5]:
            test_name = f.test_name.split("::")[-1]
            lines.append(f"    {test_name}  FAILED")
            if f.message:
                lines.append(f"      {f.message[:100]}")
        if len(goal_result.failures) > 5:
            lines.append(f"    ... and {len(goal_result.failures) - 5} more")

    converged = (
        record.compliance_score >= config.compliance_threshold
        and record.goal_score >= config.goal_threshold
    )

    if converged:
        title = f"[bold green]✓ CONVERGED[/]  iteration {record.n}/{config.max_iterations}"
        border = "green"
    else:
        title = f"[bold cyan]Phase 2 — Generation Loop[/]"
        border = "bright_blue"

    console.print(Panel("\n".join(lines), title=title, border_style=border))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
