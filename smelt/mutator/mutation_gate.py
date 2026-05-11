"""Mutation gate: validates test suite quality before freezing."""

import logging
import os
import shutil
import site
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# mutmut 2.x status values stored in the SQLite cache
_KILLED_STATUSES = {"ok_killed", "bad_timeout"}
_SURVIVED_STATUSES = {"bad_survived", "ok_suspicious"}


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
    # Build PYTHONPATH so mutmut's subprocess pytest can find packages installed
    # in the current interpreter's environment (e.g. project stubs like coffeeloop_core).
    site_packages = site.getsitepackages() if hasattr(site, "getsitepackages") else []
    user_site = site.getusersitepackages() if hasattr(site, "getusersitepackages") else ""
    extra_paths = [p for p in site_packages + ([user_site] if user_site else []) if p]
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(filter(None, [existing_pythonpath] + extra_paths))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        shutil.copy(stub_path, src_dir / f"{module_name}.py")

        tests_dir = tmp_dir / "tests"
        tests_dir.mkdir()
        # conftest adds src/ and the current interpreter's site-packages to sys.path
        # so mutmut's spawned pytest process can import both the module under test
        # and any installed packages the test suite depends on.
        site_paths_repr = repr(extra_paths)
        (tests_dir / "conftest.py").write_text(
            f"import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            f"for _p in {site_paths_repr}:\n"
            f"    if _p not in sys.path:\n"
            f"        sys.path.append(_p)\n",
            encoding="utf-8",
        )
        shutil.copy(test_path, tests_dir / test_path.name)

        subprocess_env = {**os.environ, "PYTHONPATH": pythonpath}

        # Pre-check: if the baseline fails too many tests, mutmut will report 0 mutants.
        # Allow mutmut to proceed as long as a majority of tests pass — mutmut only
        # mutates the parts of the implementation that the passing tests exercise.
        pre = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=no", "--no-header"],
            capture_output=True,
            text=True,
            cwd=tmp_dir,
            env=subprocess_env,
        )
        pre_output = pre.stdout + pre.stderr
        passed_match = __import__("re").search(r"(\d+) passed", pre_output)
        failed_match = __import__("re").search(r"(\d+) failed", pre_output)
        n_passed = int(passed_match.group(1)) if passed_match else 0
        n_failed = int(failed_match.group(1)) if failed_match else 0
        n_total = n_passed + n_failed
        if n_total > 0 and n_passed / n_total < 0.5:
            log.warning(
                "mutation_gate: baseline passes only %d/%d tests — mutmut cannot run.\n%s",
                n_passed, n_total, pre_output[-600:],
            )
            return 0.0, False
        if n_failed > 0:
            log.warning(
                "mutation_gate: baseline fails %d/%d tests — proceeding with mutmut on passing subset",
                n_failed, n_total,
            )

        result = subprocess.run(
            [
                sys.executable, "-m", "mutmut", "run",
                "--paths-to-mutate", str(src_dir.relative_to(tmp_dir)),
                "--tests-dir", str(tests_dir.relative_to(tmp_dir)),
                "--simple-output",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_dir,
            env=subprocess_env,
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
