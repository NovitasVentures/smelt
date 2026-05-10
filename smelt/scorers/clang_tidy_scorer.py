"""clang-tidy compliance scorer for C/C++ code."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from smelt.scorers.base import BaseScorer, ScoreResult, Violation

log = logging.getLogger(__name__)

_LINE_RE = re.compile(r"^(.+?):(\d+):(\d+):\s+\w+:\s+(.+?)\s+\[(.+)\]$")


class ClangTidyScorer(BaseScorer):
    """clang-tidy compliance scorer."""

    name = "clang_tidy"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        if not shutil.which("clang-tidy"):
            log.warning("ClangTidyScorer: clang-tidy not found on PATH — returning score=1.0")
            return ScoreResult(score=1.0, violations=[])

        c_files = list(code_path.rglob("*.c")) + list(code_path.rglob("*.cpp"))
        c_files = [f for f in c_files if "_build" not in f.parts]
        if not c_files:
            return ScoreResult(score=1.0, violations=[])

        checks = config.get("checks", "cert-*,bugprone-*")
        violations: list[Violation] = []
        total_lines = 0

        for c_file in c_files:
            try:
                total_lines += len(c_file.read_text(encoding="utf-8").splitlines())
            except OSError:
                continue

            result = subprocess.run(
                [
                    "clang-tidy",
                    str(c_file),
                    f"--checks={checks}",
                    "--",
                    "-std=c99",
                    f"-I{code_path}",
                ],
                capture_output=True,
                text=True,
            )
            for line in (result.stdout + result.stderr).splitlines():
                m = _LINE_RE.match(line)
                if not m:
                    continue
                file_, lineno, _col, message, rule = m.groups()
                violations.append(
                    Violation(
                        file=file_,
                        line=int(lineno),
                        rule=rule,
                        message=message.strip(),
                    )
                )

        score = 1.0 - min(len(violations) / max(total_lines, 1), 1.0)
        return ScoreResult(score=score, violations=violations)
