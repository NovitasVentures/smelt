"""Crasis architectural compliance scorer for Smelt."""

import json
import logging
from pathlib import Path

from crasis import CrasisToolkit

from smelt.scorers.base import BaseScorer, ScoreResult, Violation
from smelt.scorers.chunker import ChunkLevel, chunk_code

log = logging.getLogger(__name__)

_DEFAULT_MODELS_DIR = "specialists"
_DEFAULT_CONFIDENCE_THRESHOLD = 0.85


class CrasisScorer(BaseScorer):
    """Scores code against architectural principles using Crasis ONNX specialists.

    Each specialist covers one principle extracted from the project's architecture
    document. Inference is local ONNX — no API calls at score time.
    """

    name = "crasis"

    def __init__(self) -> None:
        self._toolkit_cache: dict[str, CrasisToolkit] = {}

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        """Score all Python files in code_path for architectural compliance.

        Config keys:
            models_dir: path to specialists directory (default: "specialists")
            confidence_threshold: float 0-1, default 0.85
            mandatory_principles: list[str] — principle names that block CONVERGED
        """
        models_dir = str(config.get("models_dir", _DEFAULT_MODELS_DIR))
        threshold = float(config.get("confidence_threshold", _DEFAULT_CONFIDENCE_THRESHOLD))
        mandatory: set[str] = set(config.get("mandatory_principles", []))

        toolkit = self._load_toolkit(models_dir)
        if not toolkit.specialists():
            return ScoreResult(score=1.0, violations=[])

        py_files = sorted(code_path.rglob("*.py"))
        if not py_files:
            return ScoreResult(score=1.0, violations=[])

        # Load per-specialist metadata (chunk_level, weight)
        specialist_meta = _load_specialist_meta(models_dir, toolkit)

        violations: list[Violation] = []
        total_chunks = 0

        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning("Cannot read %s: %s", py_file, exc)
                continue

            for specialist_name in toolkit.specialists():
                meta = specialist_meta.get(specialist_name, {})
                chunk_level = ChunkLevel(meta.get("chunk_level", "function"))
                weight = float(meta.get("weight", 1.0))
                is_mandatory = specialist_name in mandatory

                chunks = chunk_code(source, level=chunk_level, filepath=str(py_file))
                total_chunks += len(chunks)

                for chunk in chunks:
                    try:
                        result = toolkit.classify(specialist_name, chunk.text)
                    except Exception as exc:
                        log.warning("classify() failed for %s on %s: %s", specialist_name, chunk.location, exc)
                        continue

                    if result["label"] == "positive" and result["confidence"] >= threshold:
                        rule = f"ARCH:{specialist_name} [mandatory]" if is_mandatory else f"ARCH:{specialist_name}"
                        violations.append(Violation(
                            file=str(py_file),
                            line=chunk.start_line,
                            rule=rule,
                            message=(
                                f"violates '{specialist_name}' "
                                f"({result['confidence']:.0%} confidence) — {chunk.signature}"
                            ),
                        ))

        n_specialists = len(toolkit.specialists())
        score = self._aggregate(violations, total_chunks, n_specialists, specialist_meta, mandatory)
        return ScoreResult(score=score, violations=violations)

    def _load_toolkit(self, models_dir: str) -> CrasisToolkit:
        """Load and cache toolkit from models_dir. Gracefully handles missing dir.

        Crasis exports each specialist into a wrapper directory named <name>-onnx/,
        with the actual loadable ONNX package one level deeper as <name>-onnx/<name>-onnx/.
        We scan both the top level and one level deeper to find all .onnx packages.
        """
        if models_dir in self._toolkit_cache:
            return self._toolkit_cache[models_dir]

        models_path = Path(models_dir)
        if not models_path.exists():
            log.warning("CrasisScorer: models_dir '%s' not found — no specialists loaded", models_dir)
            self._toolkit_cache[models_dir] = CrasisToolkit({})
            return self._toolkit_cache[models_dir]

        # Collect all candidate package directories: both direct children and
        # grandchildren, to handle crasis's <name>-onnx/<name>-onnx/ export layout.
        package_dirs: list[Path] = []
        for child in sorted(models_path.iterdir()):
            if not child.is_dir():
                continue
            if list(child.glob("*.onnx")):
                package_dirs.append(child)
            else:
                for grandchild in sorted(child.iterdir()):
                    if grandchild.is_dir() and list(grandchild.glob("*.onnx")):
                        package_dirs.append(grandchild)

        if not package_dirs:
            log.warning("CrasisScorer: no specialist packages found in '%s'", models_dir)
            self._toolkit_cache[models_dir] = CrasisToolkit({})
            return self._toolkit_cache[models_dir]

        from crasis import Specialist
        specialists: dict[str, Specialist] = {}
        for pkg_dir in package_dirs:
            try:
                s = Specialist.load(pkg_dir)
                specialists[s.name] = s
                log.info("CrasisScorer: loaded specialist '%s' from %s", s.name, pkg_dir)
            except Exception as exc:
                log.warning("CrasisScorer: failed to load specialist from %s: %s", pkg_dir, exc)

        toolkit = CrasisToolkit(specialists)
        self._toolkit_cache[models_dir] = toolkit
        return toolkit

    def _aggregate(
        self,
        violations: list[Violation],
        n_chunks: int,
        n_specialists: int,
        specialist_meta: dict[str, dict],
        mandatory: set[str],
    ) -> float:
        """Compute compliance score: fraction of chunks that pass all specialists.

        Each chunk that has at least one violation counts as a failing chunk,
        weighted by the highest-weight principle that fired on it.
        Score = 1.0 - (sum of per-chunk penalty weights) / n_chunks
        """
        if n_chunks == 0:
            return 1.0
        if not violations:
            return 1.0

        # Group violations by (file, line) — that's the chunk identity in violations
        chunk_max_weight: dict[tuple[str, int], float] = {}
        for v in violations:
            rule_parts = v.rule.replace(" [mandatory]", "")
            specialist_name = rule_parts.removeprefix("ARCH:")
            meta = specialist_meta.get(specialist_name, {})
            weight = float(meta.get("weight", 1.0))
            key = (v.file, v.line)
            chunk_max_weight[key] = max(chunk_max_weight.get(key, 0.0), weight)

        penalty = sum(chunk_max_weight.values())
        return max(0.0, 1.0 - (penalty / n_chunks))


def _load_specialist_meta(models_dir: str, toolkit: CrasisToolkit) -> dict[str, dict]:
    """Read crasis_meta.json sidecar from each specialist directory.

    Returns dict mapping specialist_name → metadata dict with chunk_level, weight.
    Falls back to defaults if sidecar is missing.

    arch-build writes crasis_meta.json at the wrapper level:
      specialists/<name>-onnx/crasis_meta.json
    The Smelt metadata lives under the "smelt" key within that file.
    """
    meta: dict[str, dict] = {}
    models_path = Path(models_dir)

    for name in toolkit.specialists():
        # Search order: wrapper dir (arch-build convention), then direct name dirs
        candidate_sidecars = [
            models_path / f"{name}-onnx" / "crasis_meta.json",
            models_path / name / "crasis_meta.json",
        ]
        sidecar_data: dict = {}
        for sidecar in candidate_sidecars:
            if sidecar.exists():
                try:
                    raw = json.loads(sidecar.read_text(encoding="utf-8"))
                    sidecar_data = raw.get("smelt", raw)
                except (json.JSONDecodeError, OSError) as exc:
                    log.warning("Cannot read %s: %s", sidecar, exc)
                break

        if not sidecar_data:
            log.warning(
                "CrasisScorer: no crasis_meta.json for specialist '%s' — using defaults "
                "(chunk_level=function, weight=1.0). Run smelt arch-build to generate it.",
                name,
            )

        meta[name] = {
            "chunk_level": sidecar_data.get("chunk_level", "function"),
            "weight": sidecar_data.get("weight", 1.0),
        }

    return meta
