"""Mypy strict compliance scorer."""

import re
import subprocess
from pathlib import Path

from smelt.scorers.base import BaseScorer, ScoreResult, Violation

_ERROR_RE = re.compile(r"^(.+):(\d+):(?:\d+:)? error: (.+?)(?:\s+\[(.+)\])?$")


class MypyScorer(BaseScorer):
    """Scores Python code compliance using mypy --strict."""

    name = "mypy"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        """Run mypy --strict and return a normalized compliance score.

        Args:
            code_path: Directory containing generated .py files.
            config: Scorer config (unused; flags fixed to --strict --no-error-summary).

        Returns:
            ScoreResult with score = 1.0 - min(errors / lines, 1.0).
        """
        py_files = list(code_path.rglob("*.py"))
        if not py_files:
            return ScoreResult(score=1.0)

        line_count = _count_non_blank_lines(py_files)

        result = subprocess.run(
            [
                "mypy", "--strict", "--no-error-summary",
                "--no-incremental", "--cache-dir=/dev/null",
                str(code_path),
            ],
            capture_output=True,
            text=True,
        )

        violations: list[Violation] = []
        for line in result.stdout.splitlines():
            m = _ERROR_RE.match(line)
            if not m:
                continue
            filepath, lineno, message, rule = m.group(1), m.group(2), m.group(3), m.group(4)
            violations.append(
                Violation(
                    file=filepath,
                    line=int(lineno),
                    rule=f"[{rule}]" if rule else "mypy",
                    message=message,
                )
            )

        error_count = len(violations)
        score = 1.0 - min(error_count / max(line_count, 1), 1.0)
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
