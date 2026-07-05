"""Crasis architectural compliance scorer for Smelt."""

import json
import logging
from pathlib import Path

from crasis import CrasisToolkit

from smelt.scorers.base import BaseScorer, ScoreResult, Violation
from smelt.scorers.chunker import ChunkLevel, chunk_code, redact_identifiers

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
            composites: dict[str, dict] — principle name -> {violation_specialist,
                exemption_specialist, redact_for_exemption}. A composite principle
                fires iff violation_specialist fires AND exemption_specialist does
                NOT fire on the same chunk. Use this when a single small classifier
                cannot jointly learn a name-conditioned exemption and a data-flow
                violation pattern without keying on identifier shortcuts — split
                the two into separate specialists instead of one.
        """
        models_dir = str(config.get("models_dir", _DEFAULT_MODELS_DIR))
        default_threshold = float(config.get("confidence_threshold", _DEFAULT_CONFIDENCE_THRESHOLD))
        per_specialist_thresholds: dict[str, float] = {
            k: float(v) for k, v in config.get("confidence_thresholds", {}).items()
        }
        mandatory: set[str] = set(config.get("mandatory_principles", []))
        active_filter: set[str] | None = (
            set(config["active_specialists"]) if "active_specialists" in config else None
        )
        composites: dict[str, dict] = config.get("composites", {})

        toolkit = self._load_toolkit(models_dir)
        if not toolkit.specialists():
            return ScoreResult(score=1.0, violations=[])

        _CPP_IMPL_EXTENSIONS = {".cpp", ".cc", ".cxx"}
        _CPP_EXTENSIONS = {".cpp", ".h", ".hpp", ".cc", ".cxx"}

        cpp_files = sorted(
            f for f in code_path.rglob("*")
            if f.is_file() and f.suffix in _CPP_IMPL_EXTENSIONS
            and "_build" not in f.parts
        )
        py_files = sorted(code_path.rglob("*.py"))
        source_files = cpp_files if cpp_files else py_files

        if not source_files:
            return ScoreResult(score=1.0, violations=[])

        # Load per-specialist metadata (chunk_level, weight)
        specialist_meta = _load_specialist_meta(models_dir, toolkit)

        # Principles named in active_specialists may be plain specialists or
        # composite names. Composite constituents are never scored on their own.
        composite_names = set(composites.keys())
        active_principles = [
            s for s in list(toolkit.specialists()) + list(composite_names)
            if (active_filter is None or s in active_filter) and s not in _all_constituents(composites)
        ]
        # Deduplicate while preserving order (a composite name won't also appear
        # as a raw specialist name since toolkit.specialists() lists constituents).
        seen: set[str] = set()
        active_principles = [p for p in active_principles if not (p in seen or seen.add(p))]

        violations: list[Violation] = []
        total_chunks = 0

        for src_file in source_files:
            try:
                source = src_file.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning("Cannot read %s: %s", src_file, exc)
                continue

            is_cpp = src_file.suffix in _CPP_IMPL_EXTENSIONS

            for principle_name in active_principles:
                is_mandatory = principle_name in mandatory

                if principle_name in composites:
                    composite_violations, n_chunks = self._score_composite(
                        toolkit, composites[principle_name], principle_name,
                        specialist_meta, source, src_file, is_cpp, is_mandatory,
                        per_specialist_thresholds, default_threshold,
                    )
                    violations.extend(composite_violations)
                    total_chunks += n_chunks
                    continue

                specialist_name = principle_name
                meta = specialist_meta.get(specialist_name, {})
                chunk_level = ChunkLevel(meta.get("chunk_level", "function"))

                chunks = chunk_code(
                    source, level=chunk_level, filepath=str(src_file), is_cpp=is_cpp
                )
                total_chunks += len(chunks)

                threshold = per_specialist_thresholds.get(specialist_name, default_threshold)
                requires_mutation = bool(meta.get("requires_self_mutation", False))

                for chunk in chunks:
                    if requires_mutation and not chunk.mutates_self:
                        continue

                    try:
                        result = toolkit.classify(specialist_name, chunk.text)
                    except Exception as exc:
                        log.warning("classify() failed for %s on %s: %s", specialist_name, chunk.location, exc)
                        continue

                    if result["label"] == "positive" and result["confidence"] >= threshold:
                        rule = f"ARCH:{specialist_name} [mandatory]" if is_mandatory else f"ARCH:{specialist_name}"
                        violations.append(Violation(
                            file=str(src_file),
                            line=chunk.start_line,
                            rule=rule,
                            message=(
                                f"violates '{specialist_name}' "
                                f"({result['confidence']:.0%} confidence) — {chunk.signature}"
                            ),
                        ))

        n_specialists = len(active_principles)
        active_meta = dict(specialist_meta)
        for composite_name, composite_cfg in composites.items():
            if composite_name in active_principles:
                active_meta[composite_name] = _composite_meta(composite_cfg, specialist_meta)
        active_meta = {k: v for k, v in active_meta.items() if k in set(active_principles)}
        score = self._aggregate(violations, total_chunks, n_specialists, active_meta, mandatory)
        return ScoreResult(score=score, violations=violations)

    def _score_composite(
        self,
        toolkit: CrasisToolkit,
        composite_cfg: dict,
        principle_name: str,
        specialist_meta: dict[str, dict],
        source: str,
        src_file: Path,
        is_cpp: bool,
        is_mandatory: bool,
        per_specialist_thresholds: dict[str, float],
        default_threshold: float,
    ) -> tuple[list[Violation], int]:
        """Score one composite principle: violation iff violation_specialist fires
        AND exemption_specialist does not, evaluated per-chunk.

        The exemption specialist is intended to check a name/call-graph condition
        (e.g. "is this the reset-named exemption function?") on the ORIGINAL chunk
        text. The violation specialist is intended to check a data-flow condition
        (e.g. "does this clear fault state as a side effect?") and may be trained
        on identifier-redacted text (redact_for_exemption: true in config) so it
        cannot learn a shortcut keyed to a specific function or member name.
        """
        violation_specialist = composite_cfg["violation_specialist"]
        exemption_specialist = composite_cfg["exemption_specialist"]
        redact_for_violation = bool(composite_cfg.get("redact_for_violation", False))

        meta = specialist_meta.get(violation_specialist, {})
        chunk_level = ChunkLevel(meta.get("chunk_level", "function"))
        chunks = chunk_code(source, level=chunk_level, filepath=str(src_file), is_cpp=is_cpp)

        v_threshold = per_specialist_thresholds.get(violation_specialist, default_threshold)
        e_threshold = per_specialist_thresholds.get(exemption_specialist, default_threshold)

        violations: list[Violation] = []
        for chunk in chunks:
            violation_text = redact_identifiers(chunk.text) if redact_for_violation else chunk.text

            try:
                v_result = toolkit.classify(violation_specialist, violation_text)
                e_result = toolkit.classify(exemption_specialist, chunk.text)
            except Exception as exc:
                log.warning(
                    "classify() failed for composite '%s' on %s: %s",
                    principle_name, chunk.location, exc,
                )
                continue

            fires = v_result["label"] == "positive" and v_result["confidence"] >= v_threshold
            exempt = e_result["label"] == "positive" and e_result["confidence"] >= e_threshold

            if fires and not exempt:
                rule = f"ARCH:{principle_name} [mandatory]" if is_mandatory else f"ARCH:{principle_name}"
                violations.append(Violation(
                    file=str(src_file),
                    line=chunk.start_line,
                    rule=rule,
                    message=(
                        f"violates '{principle_name}' "
                        f"(violation={v_result['confidence']:.0%}, exemption={e_result['confidence']:.0%}) "
                        f"— {chunk.signature}"
                    ),
                ))

        return violations, len(chunks)

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
        """Compute compliance score: fraction of principle weight with zero violations.

        Score = 1.0 - (sum of weights of violated principles / sum of all weights)

        A principle is violated if ANY chunk triggered it anywhere in the codebase.
        One hit anywhere counts as a full principle violation, penalized by its weight.
        """
        if n_specialists == 0:
            return 1.0
        if not violations:
            return 1.0

        violated: set[str] = set()
        for v in violations:
            rule_parts = v.rule.replace(" [mandatory]", "")
            specialist_name = rule_parts.removeprefix("ARCH:")
            violated.add(specialist_name)

        total_weight = sum(
            float(specialist_meta.get(name, {}).get("weight", 1.0))
            for name in specialist_meta
        )
        if total_weight == 0:
            return 1.0

        violated_weight = sum(
            float(specialist_meta.get(name, {}).get("weight", 1.0))
            for name in violated
        )
        return max(0.0, 1.0 - violated_weight / total_weight)


def _all_constituents(composites: dict[str, dict]) -> set[str]:
    """Return every violation_specialist/exemption_specialist name referenced by
    any composite, so they can be excluded from independent per-specialist scoring."""
    constituents: set[str] = set()
    for composite_cfg in composites.values():
        constituents.add(composite_cfg["violation_specialist"])
        constituents.add(composite_cfg["exemption_specialist"])
    return constituents


def _composite_meta(composite_cfg: dict, specialist_meta: dict[str, dict]) -> dict:
    """Derive weight/chunk_level for a composite principle from its violation
    specialist's metadata (the specialist whose chunk_level governs iteration)."""
    violation_meta = specialist_meta.get(composite_cfg["violation_specialist"], {})
    return {
        "chunk_level": violation_meta.get("chunk_level", "function"),
        "weight": composite_cfg.get("weight", violation_meta.get("weight", 1.0)),
        "requires_self_mutation": violation_meta.get("requires_self_mutation", False),
    }


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
            "requires_self_mutation": sidecar_data.get("requires_self_mutation", False),
        }

    return meta
