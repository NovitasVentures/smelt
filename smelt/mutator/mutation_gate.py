"""Mutation gate: validates test suite quality before freezing."""

import logging
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# mutmut 2.x status values stored in the SQLite cache
_KILLED_STATUSES = {"ok_killed", "timeout"}
_SURVIVED_STATUSES = {"survived", "suspicious"}


def run(
    test_path: Path,
    stub_path: Path,
    threshold: float,
    module_name: str = "implementation",
) -> tuple[float, bool]:
    """Run mutmut 2.x against a stub implementation and return the mutation kill rate.

    Args:
        test_path: Path to the generated test file.
        stub_path: Path to the stub implementation file.
        threshold: Minimum kill rate required to pass (e.g. 0.70).
        module_name: Module name the tests import from.

    Returns:
        Tuple of (kill_rate, passed) where passed = kill_rate >= threshold.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy(stub_path, src_dir / f"{module_name}.py")

        tests_dir = tmp_dir / "tests"
        tests_dir.mkdir()
        # conftest so pytest finds src/ on sys.path
        (tests_dir / "conftest.py").write_text(
            f"import sys; sys.path.insert(0, '{src_dir}')\n", encoding="utf-8"
        )
        shutil.copy(test_path, tests_dir / test_path.name)

        result = subprocess.run(
            [
                "mutmut", "run",
                "--paths-to-mutate", str(src_dir),
                "--tests-dir", str(tests_dir),
                "--simple-output",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_dir,
        )
        log.debug("mutmut stdout:\n%s", result.stdout)
        log.debug("mutmut stderr:\n%s", result.stderr)

        kill_rate = _read_kill_rate(tmp_dir / ".mutmut-cache")

    passed = kill_rate >= threshold
    log.info(
        "Mutation kill rate: %.0f%% (threshold: %.0f%%)",
        kill_rate * 100,
        threshold * 100,
    )
    return kill_rate, passed


def _read_kill_rate(cache_path: Path) -> float:
    """Read kill/survived counts from mutmut's SQLite cache."""
    if not cache_path.exists():
        log.warning("mutmut cache not found at %s; defaulting kill rate to 0.0", cache_path)
        return 0.0

    try:
        con = sqlite3.connect(str(cache_path))
        cur = con.cursor()
        cur.execute("SELECT status, count(*) FROM Mutant GROUP BY status")
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error as exc:
        log.warning("Could not read mutmut cache: %s", exc)
        return 0.0

    counts: dict[str, int] = {status: count for status, count in rows}
    killed = sum(counts.get(s, 0) for s in _KILLED_STATUSES)
    survived = sum(counts.get(s, 0) for s in _SURVIVED_STATUSES)
    total = killed + survived

    if total == 0:
        log.warning("mutmut reported 0 mutants; defaulting kill rate to 0.0")
        return 0.0

    return killed / total
