"""Crasis architectural compliance scorer for Smelt."""

import json
import logging
import re
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
            composites: dict[str, dict] — principle name -> composite config.
                A composite principle fires iff its violation_specialist fires
                AND the chunk is not exempt. Keys:
                  violation_specialist: specialist name (required)
                  exemption_specialist: specialist name — learned exemption,
                      checked on the unredacted chunk
                  exemption_signatures: list[str] — deterministic exemption:
                      chunks whose method name (from CodeChunk.signature)
                      matches exactly are never violations. Use this when the
                      rule's exemption clause names exact functions — a string
                      comparison, not a learning problem.
                  (at most one of exemption_specialist/exemption_signatures)
                  trigger_patterns: list[str] — deterministic gate: regexes
                      applied to the UNREDACTED chunk text; the violation
                      specialist only evaluates chunks matching at least one.
                      Chunks matching none are structurally incapable of
                      violating the rule and are skipped without a model
                      call. May be used alone, with no exemption tier, when
                      the rule has no separate "is this permitted" question —
                      the gated model verdict is final.
                  At least one of exemption_specialist, exemption_signatures,
                  or trigger_patterns must be set — otherwise this is not a
                  composite, just violation_specialist scored directly.
                  redact_for_violation: bool — classify the violation
                      specialist on identifier-redacted text so it cannot
                      learn identifier shortcuts.
                Use a composite when a single small classifier cannot jointly
                learn a name-conditioned exemption and a data-flow violation
                pattern without keying on identifier shortcuts — compile the
                deterministic parts of the rule into the gate/exemption and
                let the model judge only what requires judgment.
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
        AND the chunk is not exempt, evaluated per-chunk.

        Deterministic tiers run first, on the ORIGINAL chunk text/signature:
        trigger_patterns gate which chunks the violation specialist sees at all,
        and exemption_signatures exempt exact method names without a model call.
        The violation specialist checks the data-flow condition (e.g. "does this
        clear fault state as a side effect?") and may be trained on
        identifier-redacted text (redact_for_violation: true) so it cannot learn
        a shortcut keyed to a specific function or member name. A learned
        exemption_specialist (mutually exclusive with exemption_signatures) is
        checked on the unredacted chunk after the violation specialist fires.
        """
        violation_specialist = composite_cfg["violation_specialist"]
        exemption_specialist = composite_cfg.get("exemption_specialist")
        exemption_signatures = composite_cfg.get("exemption_signatures")
        trigger_patterns = [re.compile(p) for p in composite_cfg.get("trigger_patterns", [])]
        delegation_call_patterns = [re.compile(p) for p in composite_cfg.get("delegation_call_patterns", [])]
        cleared_value_patterns = list(composite_cfg.get("cleared_value_patterns", []))
        if exemption_specialist is not None and exemption_signatures is not None:
            raise ValueError(
                f"composite '{principle_name}' must configure at most one of "
                "'exemption_specialist' or 'exemption_signatures'"
            )
        if (
            exemption_specialist is None and exemption_signatures is None
            and not trigger_patterns and not delegation_call_patterns and not cleared_value_patterns
        ):
            raise ValueError(
                f"composite '{principle_name}' must configure at least one of "
                "'exemption_specialist', 'exemption_signatures', 'trigger_patterns', "
                "'delegation_call_patterns', or 'cleared_value_patterns' — otherwise it "
                "is just violation_specialist alone, not a composite"
            )
        exempt_names = set(exemption_signatures or [])
        redact_for_violation = bool(composite_cfg.get("redact_for_violation", False))
        preserve_prefixes = tuple(composite_cfg.get("redaction_preserve_prefixes", []))

        meta = specialist_meta.get(violation_specialist, {})
        chunk_level = ChunkLevel(meta.get("chunk_level", "function"))
        chunks = chunk_code(source, level=chunk_level, filepath=str(src_file), is_cpp=is_cpp)

        v_threshold = per_specialist_thresholds.get(violation_specialist, default_threshold)

        violations: list[Violation] = []
        for chunk in chunks:
            if trigger_patterns and not any(p.search(chunk.text) for p in trigger_patterns):
                continue
            if exempt_names and _method_name_from_signature(chunk.signature) in exempt_names:
                continue

            delegation_verdict = _delegation_call_verdict(chunk.text, delegation_call_patterns)
            if delegation_verdict is not None:
                if delegation_verdict:
                    rule = f"ARCH:{principle_name} [mandatory]" if is_mandatory else f"ARCH:{principle_name}"
                    violations.append(Violation(
                        file=str(src_file),
                        line=chunk.start_line,
                        rule=rule,
                        message=(
                            f"violates '{principle_name}' "
                            f"(delegation call followed by further work, no model call) "
                            f"— {chunk.signature}"
                        ),
                    ))
                continue

            if cleared_value_patterns:
                if _cleared_value_assignment_verdict(chunk.text, cleared_value_patterns):
                    rule = f"ARCH:{principle_name} [mandatory]" if is_mandatory else f"ARCH:{principle_name}"
                    violations.append(Violation(
                        file=str(src_file),
                        line=chunk.start_line,
                        rule=rule,
                        message=(
                            f"violates '{principle_name}' "
                            f"(cleared-value member assignment, no model call) "
                            f"— {chunk.signature}"
                        ),
                    ))
                # False is authoritative here, not "no opinion": this chunk
                # passed the trigger gate and found no delegation-call match
                # (checked above), so the only reason it is in this branch at
                # all is the presence of a cleared-value literal somewhere in
                # its text — a comparison or local-variable use, per this
                # function's contract. There is no remaining mechanism (this
                # composite has none) that could turn that into a violation,
                # so skip the model rather than let a redaction-blinded
                # judgment override a structural fact.
                continue

            violation_text = (
                redact_identifiers(chunk.text, preserve_prefixes=preserve_prefixes)
                if redact_for_violation else chunk.text
            )
            try:
                v_result = toolkit.classify(violation_specialist, violation_text)
            except Exception as exc:
                log.warning(
                    "classify() failed for composite '%s' on %s: %s",
                    principle_name, chunk.location, exc,
                )
                continue

            fires = v_result["label"] == "positive" and v_result["confidence"] >= v_threshold
            if not fires:
                continue

            if exemption_specialist is not None:
                e_threshold = per_specialist_thresholds.get(exemption_specialist, default_threshold)
                try:
                    e_result = toolkit.classify(exemption_specialist, chunk.text)
                except Exception as exc:
                    log.warning(
                        "classify() failed for composite '%s' on %s: %s",
                        principle_name, chunk.location, exc,
                    )
                    continue
                if e_result["label"] == "positive" and e_result["confidence"] >= e_threshold:
                    continue
                detail = (
                    f"violation={v_result['confidence']:.0%}, "
                    f"exemption={e_result['confidence']:.0%}"
                )
            elif exempt_names:
                detail = f"violation={v_result['confidence']:.0%}, no name exemption"
            else:
                detail = f"violation={v_result['confidence']:.0%}"

            rule = f"ARCH:{principle_name} [mandatory]" if is_mandatory else f"ARCH:{principle_name}"
            violations.append(Violation(
                file=str(src_file),
                line=chunk.start_line,
                rule=rule,
                message=f"violates '{principle_name}' ({detail}) — {chunk.signature}",
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


def _cleared_value_assignment_verdict(chunk_text: str, cleared_value_patterns: list[str]) -> bool:
    """Deterministic verdict for "is a cleared value assigned to a member?"

    Returns True if any of `cleared_value_patterns` (each a literal value the
    rule calls "cleared", e.g. "FaultType::NONE") is assigned — via a direct
    or array-indexed trailing-underscore member, or via a range-based loop
    variable bound to a trailing-underscore member container — to a member.
    Returns False otherwise (the value may appear in a comparison or a
    local-variable assignment, which this deliberately does not count as a
    clearing assignment).

    Callers treat False as authoritative (a clean verdict, not "no opinion")
    ONLY when the chunk is known by some other means to actually contain one
    of `cleared_value_patterns` — e.g. because trigger_patterns already
    required it and no other deterministic tier (like a delegation-call
    check) matched first. If the chunk might not contain the value at all,
    False alone does not establish that; check with something like
    `value in chunk_text` first, or fall through to a learned specialist.

    This exists because after identifier redaction (which a violation
    specialist needs to avoid keying on project vocabulary), a member
    assignment (`MEMBER_0 = FaultType::NONE`) and a local-variable assignment
    of the identical literal (`FaultType current = FaultType::NONE`) become
    structurally close — the chunker's own member-vs-local distinction (the
    trailing underscore) survives redaction and is a hard structural fact,
    not something a small classifier reliably learns from naturally-generated
    training data (see demo/bms/specialist_authoring.md build history for a
    case where it did not).
    """
    for value in cleared_value_patterns:
        # Direct or array-indexed trailing-underscore member assignment.
        if re.search(rf'\b\w+_\s*(?:\[[^\]]*\])?\s*=\s*{re.escape(value)}\b', chunk_text):
            return True
        # Range-based loop over a trailing-underscore member container whose
        # loop variable is assigned the cleared value: for (auto& x : m_) { x = V; }
        for loop_match in re.finditer(r'for\s*\(\s*auto\s*&\s*(\w+)\s*:\s*\w+_\s*\)', chunk_text):
            loop_var = loop_match.group(1)
            if re.search(rf'\b{re.escape(loop_var)}\s*=\s*{re.escape(value)}\b', chunk_text):
                return True
    return False


def _delegation_call_verdict(chunk_text: str, patterns: list["re.Pattern[str]"]) -> bool | None:
    """Deterministic verdict for a "delegates to a named routine" ambiguity.

    Returns True (violation) if a call matching one of `patterns` is followed
    by further work in the same function body (anything beyond an optional
    trailing return and closing braces) — the call's effect is undone or
    supplemented by subsequent statements, e.g. "reset the state, then
    recompute it" (reinit-before-evaluate). Returns False (clean) if the
    matched call is essentially the entire body (a pure delegation wrapper,
    optionally preceded by a guard clause and/or followed only by a bare
    return) — the function defers entirely to the callee. Returns None if no
    pattern matches, meaning this mechanism has no opinion and the caller
    should fall through to the next tier (e.g. a learned specialist).

    This exists because "does the body do anything after calling X" is a
    question about control-flow shape, not identifier meaning — deciding it
    with a trained classifier invites exactly the token-correlation shortcut
    this composite architecture exists to avoid (see
    demo/bms/specialist_authoring.md build history for a case where a single
    classifier could not reliably separate these two shapes from
    naturally-generated training data).
    """
    for pattern in patterns:
        match = pattern.search(chunk_text)
        if not match:
            continue
        rest = chunk_text[match.end():]
        rest = re.sub(r"\s+", " ", rest).strip()
        rest = re.sub(r"return\s+[^;]*;\s*\}*\s*$", "", rest).strip()
        rest = rest.rstrip("}").strip()
        return len(rest) > 0
    return None


def _method_name_from_signature(signature: str) -> str:
    """Extract the bare method/function name from a CodeChunk signature.

    C++ chunks carry the full declaration up to the brace
    ("void FaultManager::reset_faults()"); Python chunks carry
    "ClassName.method_name" or "function_name". In both forms the method name
    is the last identifier before the first '(' (or in the whole string when
    there are no parens).
    """
    head = signature.split("(", 1)[0]
    identifiers = re.findall(r"\w+", head)
    return identifiers[-1] if identifiers else ""


def _all_constituents(composites: dict[str, dict]) -> set[str]:
    """Return every violation_specialist/exemption_specialist name referenced by
    any composite, so they can be excluded from independent per-specialist scoring."""
    constituents: set[str] = set()
    for composite_cfg in composites.values():
        constituents.add(composite_cfg["violation_specialist"])
        if composite_cfg.get("exemption_specialist") is not None:
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
