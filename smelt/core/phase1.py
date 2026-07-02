"""Phase 1: test synthesis and mutation gating."""

import hashlib
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from smelt.config.settings import SmeltConfig
from smelt.llm import client as llm
from smelt.mutator import mutation_gate

log = logging.getLogger(__name__)

_TEST_GEN_SYSTEM_PYTHON = """\
You are generating a pytest test suite from a spec and test goals.
Tests must be non-trivial — do not write tests that pass on a stub \
implementation that returns None or 0.
Cover every behavior described in the test goals. Use parametrize for \
input variations where sensible.
Import the implementation from a module named `{module_name}`.
Output ONLY the test file. No explanation. No markdown fences."""

_TEST_GEN_SYSTEM_C = """\
You are generating a GTest C++ test harness for a C implementation named `{module_name}`.
The C source file will be `{module_name}.c` and header `{module_name}.h`.
Include the C header with an extern "C" block:
  extern "C" {{
    #include "{module_name}.h"
  }}
Tests must be non-trivial — do not write tests that pass on a stub returning 0 for everything.
Cover every behavior described in the test goals.
Use TEST(SuiteName, TestName_Scenario_ExpectedOutcome) naming.
Use ASSERT_* for preconditions that make further testing meaningless.
Use EXPECT_* for all other assertions.
Do NOT use dynamic memory in tests (no new, no malloc).
Output ONLY the .cpp test file. No explanation. No markdown fences."""

_TEST_GEN_SYSTEM_CPP = """\
You are generating a GTest C++14 test harness for a multi-file C++ implementation.
The implementation will have multiple header and source files in subdirectories:
  common/error_code.h, common/sensor_id.h (or similar shared types)
  hal/*.h, hal/*.cpp
  processing/*.h, processing/*.cpp
  application/*.h, application/*.cpp

Include headers directly by their subdirectory paths:
  #include "common/error_code.h"
  #include "hal/sensor_driver.h"
  #include "processing/sensor_processor.h"
  #include "application/sensor_dispatcher.h"

Do NOT use extern "C" blocks — the implementation is C++, not C.
Do NOT include a flat `{module_name}.h` — the implementation has no such umbrella header.

Tests must be non-trivial — do not write tests that pass on a stub.
Cover every behavior described in the test goals.
Use TEST(SuiteName, TestName_Scenario_ExpectedOutcome) naming.
Use ASSERT_* for preconditions that make further testing meaningless.
Use EXPECT_* for all other assertions.
Do NOT use dynamic memory in tests (no new, no delete).
Output ONLY the .cpp test file. No explanation. No markdown fences."""

_BASELINE_GEN_SYSTEM_PYTHON = """\
You are generating a working Python implementation from a spec and test file.
The implementation must make ALL tests in the test suite pass — this is used as \
a baseline for mutation testing, not as the final deliverable.
Rules:
- All packages imported by the test file are installed and available. Import and use \
them exactly as the tests do — do NOT redefine or stub types that are imported from \
external packages.
- If tests check isinstance(result, SomeClass) where SomeClass comes from an external \
package, your implementation must return actual instances of that class.
- Do NOT use eval(), exec(), or compile() — mutation testing cannot instrument these.
- Do NOT use import statements inside function bodies — put all imports at module level.
- Implement the logic directly with plain Python control flow.
Output ONLY the Python file. No explanation. No markdown fences."""

_BASELINE_GEN_SYSTEM_C = """\
You are generating a minimal stub C implementation for mutation testing scaffolding.
The stub just needs to compile and link with a GTest harness — it does not need to pass tests.
Provide both a header and implementation using this exact delimiter format:
--- HEADER ---
(header file content)
--- SOURCE ---
(source file content)
All functions should return 0 or a zero-equivalent status. No dynamic memory.
Output ONLY the two sections above. No explanation. No markdown fences."""

_REGEN_SUFFIX = """\

PREVIOUS ATTEMPT FAILED THE MUTATION GATE:
Kill rate: {kill_rate:.0%} (required: {threshold:.0%})
Your tests were too weak — a stub implementation survived too many mutations.
Strengthen assertions. Add boundary tests. Make tests fail on trivially \
incorrect behavior.
Regenerate the test file now."""

MAX_GATE_ATTEMPTS = 3


def run(
    spec: str,
    goals: str,
    config: SmeltConfig,
    output_dir: Path,
    run_id: str,
    module_name: str = "implementation",
) -> Path:
    """Synthesize a test suite, validate with mutation gate, and freeze it.

    Args:
        spec: Natural language specification text.
        goals: Test goal descriptions.
        config: Smelt runtime config.
        output_dir: Root output directory for this run.
        run_id: Unique run identifier (used in manifest).
        module_name: Module name the tests will import/include.

    Returns:
        Path to the frozen test file.

    Raises:
        RuntimeError: If mutation gate never passes within MAX_GATE_ATTEMPTS.
    """
    if config.language in ("c", "cpp"):
        return _run_c(spec, goals, config, output_dir, run_id, module_name)
    return _run_python(spec, goals, config, output_dir, run_id, module_name)


def _run_python(
    spec: str,
    goals: str,
    config: SmeltConfig,
    output_dir: Path,
    run_id: str,
    module_name: str,
) -> Path:
    frozen_dir = output_dir / "frozen_tests"
    frozen_dir.mkdir(parents=True, exist_ok=True)

    spec_hash = _sha256(spec)
    user_prompt = _build_test_gen_prompt(spec, goals)
    kill_rate = 0.0

    for attempt in range(1, MAX_GATE_ATTEMPTS + 1):
        log.info("Phase 1: generating test suite (attempt %d/%d)", attempt, MAX_GATE_ATTEMPTS)

        if attempt > 1:
            user_prompt = _build_test_gen_prompt(spec, goals) + _REGEN_SUFFIX.format(
                kill_rate=kill_rate,
                threshold=config.mutation_threshold,
            )

        test_source = llm.complete(
            system=_TEST_GEN_SYSTEM_PYTHON.format(module_name=module_name),
            user=user_prompt,
            model=config.model,
            max_tokens=config.max_tokens,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            test_file = tmp_dir / f"test_{module_name}.py"
            test_file.write_text(test_source, encoding="utf-8")

            log.info("Phase 1: generating baseline implementation for mutation gate")
            # Extract all external imports from the test file so the LLM knows
            # which packages are available as installed dependencies.
            import re as _re
            external_imports = sorted(set(_re.findall(
                r"^(?:from|import)\s+([\w.]+)", test_source, _re.MULTILINE
            )) - {module_name, "pytest", "unittest", "conftest"})
            imports_note = (
                f"\nThe test file imports from these installed packages: "
                f"{', '.join(external_imports)}. "
                f"Import and use them directly — do NOT redefine these types locally."
                if external_imports else ""
            )
            baseline_source = llm.complete(
                system=_BASELINE_GEN_SYSTEM_PYTHON,
                user=(
                    f"SPEC:\n{spec}\n\nTEST FILE:\n{test_source}\n\n"
                    f"Generate a working implementation for module `{module_name}` "
                    f"that passes the test suite.{imports_note}"
                ),
                model=config.model,
                max_tokens=config.max_tokens,
            )

            baseline_file = tmp_dir / f"{module_name}.py"
            baseline_file.write_text(baseline_source, encoding="utf-8")
            log.debug("Phase 1: baseline implementation:\n%s", baseline_source)

            log.info(
                "Phase 1: running mutation gate (threshold=%.0f%%)",
                config.mutation_threshold * 100,
            )
            kill_rate, passed = mutation_gate.run(
                test_path=test_file,
                stub_path=baseline_file,
                threshold=config.mutation_threshold,
                module_name=module_name,
            )

            if passed:
                log.info("Phase 1: mutation gate passed (kill rate=%.0f%%)", kill_rate * 100)
                frozen_path = frozen_dir / f"test_{module_name}.py"
                shutil.copy(test_file, frozen_path)
                _write_manifest(output_dir, run_id, spec, module_name, config, test_source, kill_rate)
                return frozen_path

            log.warning(
                "Phase 1: mutation gate failed (kill rate=%.0f%%, attempt %d/%d)",
                kill_rate * 100,
                attempt,
                MAX_GATE_ATTEMPTS,
            )

    raise RuntimeError(
        f"Phase 1 failed: mutation gate did not pass after {MAX_GATE_ATTEMPTS} attempts. "
        f"Last kill rate: {kill_rate:.0%} (required: {config.mutation_threshold:.0%})"
    )


def _run_c(
    spec: str,
    goals: str,
    config: SmeltConfig,
    output_dir: Path,
    run_id: str,
    module_name: str,
) -> Path:
    """Phase 1 for C/C++: generate GTest harness, bypass mutation gate if mutate++ unavailable."""
    frozen_dir = output_dir / "frozen_tests"
    frozen_dir.mkdir(parents=True, exist_ok=True)

    user_prompt = _build_test_gen_prompt(spec, goals)
    lang = config.language.upper()

    log.info("Phase 1 (%s): generating GTest test harness", lang)
    test_gen_system = (
        _TEST_GEN_SYSTEM_CPP.format(module_name=module_name)
        if config.language == "cpp"
        else _TEST_GEN_SYSTEM_C.format(module_name=module_name)
    )
    test_source = llm.complete(
        system=test_gen_system,
        user=user_prompt,
        model=config.model,
        max_tokens=config.max_tokens,
    )

    frozen_path = frozen_dir / f"test_{module_name}.cpp"
    frozen_path.write_text(test_source, encoding="utf-8")

    # Mutation gate: bypass if mutate++ is not installed
    kill_rate: float | None = None
    engine = config.mutation_engine
    if shutil.which(engine):
        log.info("Phase 1 (%s): mutation gate via %s (not yet implemented — bypassing)", lang, engine)
        kill_rate = None
    else:
        log.warning(
            "Phase 1 (%s): %s not found on PATH. Mutation gate bypassed. "
            "Active scorers remain in effect.",
            config.language.upper(),
            engine,
        )

    _write_manifest(output_dir, run_id, spec, module_name, config, test_source, kill_rate)
    return frozen_path


def _write_manifest(
    output_dir: Path,
    run_id: str,
    spec: str,
    module_name: str,
    config: SmeltConfig,
    test_source: str,
    kill_rate: float | None,
) -> None:
    manifest = {
        "run_id": run_id,
        "spec_hash": _sha256(spec),
        "test_hash": _sha256(test_source),
        "module_name": module_name,
        "profile": config.profile,
        "language": config.language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mutation_kill_rate": kill_rate,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _build_test_gen_prompt(spec: str, goals: str) -> str:
    return f"SPEC:\n{spec}\n\nTEST GOALS:\n{goals}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
