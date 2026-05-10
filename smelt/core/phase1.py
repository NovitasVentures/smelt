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

_TEST_GEN_SYSTEM_TEMPLATE = """\
You are generating a pytest test suite from a spec and test goals.
Tests must be non-trivial — do not write tests that pass on a stub \
implementation that returns None or 0.
Cover every behavior described in the test goals. Use parametrize for \
input variations where sensible.
Import the implementation from a module named `{module_name}`.
Output ONLY the test file. No explanation. No markdown fences."""

_BASELINE_GEN_SYSTEM = """\
You are generating a working Python implementation from a spec and test file.
The implementation must make the test suite pass — this is used as a baseline \
for mutation testing, not as the final deliverable.
Rules:
- Do NOT use eval(), exec(), or compile() — mutation testing cannot instrument these.
- Do NOT use import statements inside function bodies — put all imports at module level.
- Implement the logic directly with plain Python control flow.
Output ONLY the Python file. No explanation. No markdown fences."""

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
        module_name: Python module name the tests will import from.

    Returns:
        Path to the frozen test file.

    Raises:
        RuntimeError: If mutation gate never passes within MAX_GATE_ATTEMPTS.
    """
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
            system=_TEST_GEN_SYSTEM_TEMPLATE.format(module_name=module_name),
            user=user_prompt,
            model=config.model,
            max_tokens=config.max_tokens,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            test_file = tmp_dir / f"test_{module_name}.py"
            test_file.write_text(test_source, encoding="utf-8")

            log.info("Phase 1: generating baseline implementation for mutation gate")
            baseline_source = llm.complete(
                system=_BASELINE_GEN_SYSTEM,
                user=f"SPEC:\n{spec}\n\nTEST FILE:\n{test_source}\n\n"
                     f"Generate a working implementation for module `{module_name}` "
                     f"that passes the test suite.",
                model=config.model,
                max_tokens=config.max_tokens,
            )

            baseline_file = tmp_dir / f"{module_name}.py"
            baseline_file.write_text(baseline_source, encoding="utf-8")

            log.info("Phase 1: running mutation gate (threshold=%.0f%%)", config.mutation_threshold * 100)
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

                test_hash = _sha256(test_source)
                manifest = {
                    "run_id": run_id,
                    "spec_hash": spec_hash,
                    "test_hash": test_hash,
                    "module_name": module_name,
                    "profile": config.profile,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "mutation_kill_rate": kill_rate,
                }
                (output_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )
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


def _build_test_gen_prompt(spec: str, goals: str) -> str:
    return f"SPEC:\n{spec}\n\nTEST GOALS:\n{goals}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
