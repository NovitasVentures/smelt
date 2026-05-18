"""Layer isolation scorer — detects forbidden cross-layer #include dependencies."""

import logging
import re
from pathlib import Path

from smelt.scorers.base import BaseScorer, ScoreResult, Violation

log = logging.getLogger(__name__)

_INCLUDE_RE = re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]', re.MULTILINE)

# Score degrades linearly: each violation beyond the first costs 0.2.
# Five or more violations scores 0.0.
_VIOLATIONS_TO_ZERO = 5


class LayerScorer(BaseScorer):
    """Scores C/C++ source for layer isolation violations.

    Parses #include directives across all source files, maps each file to
    a declared layer by directory prefix, and reports any include that crosses
    a forbidden layer boundary as defined in the profile config.

    Config keys:
        layers:   list[str] — layer directory names in dependency order (e.g. ["hal", "processing", "application"])
        allowed:  list[dict] — permitted dependency edges, each {"from": str, "to": str}
        mandatory: bool — if True, any violation blocks CONVERGED exit (default True)
    """

    name = "layer"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        layers: list[str] = config.get("layers", [])
        allowed_raw: list[dict] = config.get("allowed", [])
        is_mandatory: bool = bool(config.get("mandatory", True))

        if not layers:
            log.warning("LayerScorer: no layers configured — skipping")
            return ScoreResult(score=1.0, violations=[])

        allowed: set[tuple[str, str]] = {
            (edge["from"], edge["to"]) for edge in allowed_raw
        }

        layer_set = set(layers)
        violations: list[Violation] = []

        cpp_extensions = {".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx"}
        source_files = [
            f for f in sorted(code_path.rglob("*"))
            if f.is_file() and f.suffix in cpp_extensions
        ]

        for src_file in source_files:
            src_layer = _layer_of(src_file, code_path, layer_set)
            if src_layer is None:
                continue

            try:
                source = src_file.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning("LayerScorer: cannot read %s: %s", src_file, exc)
                continue

            for match in _INCLUDE_RE.finditer(source):
                include_path = match.group(1)
                included_layer = _layer_of_include(include_path, layer_set)
                if included_layer is None or included_layer == src_layer:
                    continue

                edge = (src_layer, included_layer)
                if edge not in allowed:
                    line_num = source[: match.start()].count("\n") + 1
                    rel = src_file.relative_to(code_path)
                    rule = "LAYER:layer-isolation [mandatory]" if is_mandatory else "LAYER:layer-isolation"
                    violations.append(Violation(
                        file=str(rel),
                        line=line_num,
                        rule=rule,
                        message=(
                            f"{rel} includes {include_path!r} — "
                            f"forbidden dependency: {src_layer!r} must not depend on {included_layer!r} directly"
                        ),
                    ))

        score = _compute_score(len(violations))
        return ScoreResult(score=score, violations=violations)


def _layer_of(file_path: Path, code_path: Path, layer_set: set[str]) -> str | None:
    """Return the layer name for a source file based on its directory prefix."""
    try:
        rel = file_path.relative_to(code_path)
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    return top if top in layer_set else None


def _layer_of_include(include_path: str, layer_set: set[str]) -> str | None:
    """Return the layer name referenced by an #include path, or None if not a layer header."""
    parts = include_path.replace("\\", "/").split("/")
    if not parts:
        return None
    top = parts[0]
    return top if top in layer_set else None


def _compute_score(n_violations: int) -> float:
    if n_violations == 0:
        return 1.0
    return max(0.0, 1.0 - n_violations / float(_VIOLATIONS_TO_ZERO))
