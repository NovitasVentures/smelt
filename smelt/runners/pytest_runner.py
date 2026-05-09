"""Pytest test runner."""

import os
import re
import subprocess
from pathlib import Path

from smelt.runners.base import BaseRunner, Failure, RunResult


class PytestRunner(BaseRunner):
    """Runs pytest and parses text output for pass/fail detail."""

    name = "pytest"

    def run(self, test_path: Path, code_path: Path, config: dict) -> RunResult:
        """Execute pytest with the frozen tests and generated code on sys.path.

        Args:
            test_path: Path to frozen test file or directory.
            code_path: Directory to prepend to PYTHONPATH.
            config: Runner config (unused).

        Returns:
            RunResult with goal_score = passed / total.
        """
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{code_path}:{existing}" if existing else str(code_path)

        result = subprocess.run(
            ["pytest", str(test_path), "-v", "--tb=short", "--no-header", "-q"],
            capture_output=True,
            text=True,
            env=env,
        )

        return _parse_output(result.stdout + result.stderr)


def _parse_output(output: str) -> RunResult:
    """Parse pytest -v --tb=short output into a RunResult."""
    passed = 0
    failed = 0
    failures: list[Failure] = []

    # Summary line: "3 passed, 2 failed"
    summary_match = re.search(
        r"(\d+) passed(?:.*?(\d+) failed)?|(\d+) failed(?:.*?(\d+) passed)?",
        output,
    )
    if summary_match:
        if summary_match.group(1) is not None:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2) or 0)
        elif summary_match.group(3) is not None:
            failed = int(summary_match.group(3))
            passed = int(summary_match.group(4) or 0)

    # Extract per-failure blocks from short tb output
    # Blocks start with "FAILED test_foo.py::test_name" lines
    fail_names = re.findall(r"FAILED\s+([\w/.::-]+)", output)

    # Extract short tb sections — separated by double newlines or FAILED markers
    tb_blocks = re.split(r"\n_+\s*\n", output)
    tb_map: dict[str, str] = {}
    for block in tb_blocks:
        name_match = re.search(r"(test_\w+)\s+FAILED", block)
        if name_match:
            tb_map[name_match.group(1)] = block.strip()

    for name in fail_names:
        short_name = name.split("::")[-1]
        tb = tb_map.get(short_name, "")
        # Extract assertion message from traceback
        msg_match = re.search(r"(AssertionError|Exception|Error)[^\n]*\n([^\n]+)", tb)
        message = msg_match.group(0).strip() if msg_match else name
        failures.append(Failure(test_name=name, message=message, traceback=tb))

    # Fallback: if summary parse failed but output has error indicators
    if passed == 0 and failed == 0:
        if "error" in output.lower() or "failed" in output.lower():
            failed = max(len(fail_names), 1)

    return RunResult(passed=passed, failed=failed, failures=failures)
