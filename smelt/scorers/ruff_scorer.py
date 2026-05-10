"""Ruff compliance scorer."""

import json
import subprocess
from pathlib import Path

from smelt.scorers.base import BaseScorer, ScoreResult, Violation


class RuffScorer(BaseScorer):
    """Scores Python code compliance using ruff."""

    name = "ruff"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        """Run ruff and return a normalized compliance score.

        Args:
            code_path: Directory containing generated .py files.
            config: Scorer config (unused for ruff defaults).

        Returns:
            ScoreResult with score = 1.0 - min(violations / lines, 1.0).
        """
        py_files = list(code_path.rglob("*.py"))
        if not py_files:
            return ScoreResult(score=1.0)

        line_count = _count_non_blank_lines(py_files)

        select = config.get("select", [])
        select_args = ["--select", ",".join(select)] if select else []

        result = subprocess.run(
            ["ruff", "check", str(code_path), "--output-format=json", "--isolated"] + select_args,
            capture_output=True,
            text=True,
        )

        violations: list[Violation] = []
        if result.stdout.strip():
            try:
                raw = json.loads(result.stdout)
                for item in raw:
                    violations.append(
                        Violation(
                            file=item.get("filename", ""),
                            line=item.get("location", {}).get("row", 0),
                            rule=item.get("code", ""),
                            message=item.get("message", ""),
                        )
                    )
            except json.JSONDecodeError:
                pass

        violation_count = len(violations)
        score = 1.0 - min(violation_count / max(line_count, 1), 1.0)
        return ScoreResult(score=score, violations=violations)


def _count_non_blank_lines(files: list[Path]) -> int:
    """Count non-blank lines across a list of Python files."""
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
            total += sum(1 for line in text.splitlines() if line.strip())
        except OSError:
            pass
    return total
