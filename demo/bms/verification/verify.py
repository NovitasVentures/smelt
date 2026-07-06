#!/usr/bin/env python3
"""Verification harness for Demo 8 BMS Crasis specialists.

Runs every case file in cases/<specialist>/{pos,neg}__*.cpp through the
matching ONNX specialist model and checks it against the acceptance rule in
demo/bms/specialist_authoring.md Step 3:

    - positive (violation) cases must score above 0.85
    - negative (clean) cases must score below 0.80
    - a negative in [0.80, 0.85) is a FAIL: "add negatives and rebuild --
      no threshold tuning" (there is no fixup available for a reused model)

Case files are routed through the production chunker (`chunk_code`) exactly as
`CrasisScorer` routes generated code, so the harness measures what production
sees: constructor definitions are skipped, chunk text starts at the signature
line, and a case that yields no function-level chunk is never scored in
production (PASS for a clean case, FAIL for a violation case — an invisible
violation is a real defect).

Composite principles are verified with the same trigger-gate / name-exemption /
violation-specialist pipeline `CrasisScorer._score_composite` uses, with the
composite configuration loaded directly from the active profile TOML so the
harness and the real scoring path cannot drift apart.

The "score" reported here is a single violation-likelihood number in [0, 1],
derived from the specialist's raw (label, confidence) output:

    score = confidence            if label == "positive"
    score = 1 - confidence        if label == "negative"

For a case yielding multiple chunks, the case score is the maximum chunk score
(any violating chunk fails a clean case; any firing chunk passes a violation
case) — matching how CrasisScorer reports per-chunk violations.

Usage:
    python3 verify.py                       # verify every specialist with a model present
    python3 verify.py --only <specialist>   # verify a single specialist
    python3 verify.py --models-dir <path>   # override the default models directory
    python3 verify.py --profile <path>      # override the profile TOML (composites source)

Exit code is nonzero if any case fails.
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from smelt.scorers.chunker import ChunkLevel, CodeChunk, chunk_code, redact_identifiers
from smelt.scorers.crasis_scorer import (
    _cleared_value_assignment_verdict,
    _delegation_call_verdict,
    _method_name_from_signature,
)

VERIFICATION_DIR = Path(__file__).resolve().parent
CASES_DIR = VERIFICATION_DIR / "cases"
DEFAULT_MODELS_DIR = VERIFICATION_DIR.parent / "specialists"
DEFAULT_PROFILE = VERIFICATION_DIR.parents[2] / "smelt" / "config" / "profiles" / "demo8_bms.toml"
REPORT_PATH = VERIFICATION_DIR / "report.md"

POS_THRESHOLD = 0.85  # violation cases must score strictly above this
NEG_THRESHOLD = 0.80  # clean cases must score strictly below this

# Maps specialist name -> subdirectory layout under --models-dir, matching
# the nested export structure crasis arch-build produces:
#   <models-dir>/<specialist>-onnx/<specialist>-onnx/
MODEL_SUBPATH = "{name}-onnx/{name}-onnx"


@dataclass
class CaseResult:
    specialist: str
    case_file: str
    expected: str  # "positive" or "negative"
    label: str
    confidence: float
    score: float
    verdict: str  # PASS or FAIL
    message: str = ""


def load_crasis_config(profile_path: Path) -> tuple[dict[str, dict], set[str]]:
    """Read [scorers.crasis] composites and mandatory_principles from the profile.

    The harness applies the exact configuration production uses — no duplicated
    dict to keep in sync. mandatory_principles drives the overall verdict: a
    non-mandatory specialist's failures are reported but cannot block, matching
    what non-mandatory means in the loop (cannot block CONVERGED).
    """
    with profile_path.open("rb") as fh:
        profile = tomllib.load(fh)
    crasis = profile.get("scorers", {}).get("crasis", {})
    return crasis.get("composites", {}), set(crasis.get("mandatory_principles", []))


def resolve_model_dir(models_dir: Path, specialist: str) -> Path:
    return models_dir / MODEL_SUBPATH.format(name=specialist)


def expected_from_filename(path: Path) -> str | None:
    stem = path.name
    if stem.startswith("pos__"):
        return "positive"
    if stem.startswith("neg__"):
        return "negative"
    return None


def production_chunks(text: str, case_name: str) -> list[CodeChunk]:
    """Chunk a case file the way CrasisScorer chunks generated code.

    Only FUNCTION-level chunks are returned. `_chunk_cpp_functions` falls back
    to a FILE-level chunk when a file defines no functions (e.g. an isolated
    constructor, which the chunker deliberately skips) — but generated .cpp
    implementation files always define real functions, so that fallback shape
    never reaches a specialist in production and is excluded here.
    """
    chunks = chunk_code(text, level=ChunkLevel.FUNCTION, filepath=case_name, is_cpp=True)
    return [c for c in chunks if c.level == ChunkLevel.FUNCTION]


def violation_score(label: str, confidence: float) -> float:
    if label == "positive":
        return confidence
    return 1.0 - confidence


def judge(expected: str, score: float) -> tuple[str, str]:
    """Apply the Step 3 acceptance rule. Returns (verdict, message)."""
    if expected == "positive":
        if score > POS_THRESHOLD:
            return "PASS", ""
        return "FAIL", f"violation case scored {score:.4f}, required > {POS_THRESHOLD}"
    # expected == "negative"
    if score < NEG_THRESHOLD:
        return "PASS", ""
    if score < POS_THRESHOLD:
        return "FAIL", "add negatives and rebuild — no threshold tuning"
    return "FAIL", f"clean case scored {score:.4f}, required < {NEG_THRESHOLD}"


def judge_unscored(expected: str) -> tuple[str, str]:
    """Verdict for a case the production chunker never scores (no function chunk)."""
    if expected == "negative":
        return "PASS", "never scored in production (chunker yields no function-level chunk)"
    return "FAIL", "violation invisible in production (chunker yields no function-level chunk)"


def verify_specialist(name: str, models_dir: Path) -> list[CaseResult]:
    case_dir = CASES_DIR / name
    if not case_dir.is_dir():
        print(f"warning: no case directory for specialist '{name}' at {case_dir}", file=sys.stderr)
        return []

    model_dir = resolve_model_dir(models_dir, name)
    if not model_dir.is_dir():
        print(f"warning: no model directory for specialist '{name}' at {model_dir} — skipping", file=sys.stderr)
        return []

    from crasis import Specialist

    specialist = Specialist.load(model_dir)

    results: list[CaseResult] = []
    case_files = sorted(case_dir.glob("*.cpp"))
    if not case_files:
        print(f"warning: no .cpp case files found in {case_dir}", file=sys.stderr)
        return []

    for case_file in case_files:
        expected = expected_from_filename(case_file)
        if expected is None:
            print(f"warning: skipping {case_file.name} — does not start with pos__ or neg__", file=sys.stderr)
            continue

        chunks = production_chunks(case_file.read_text(encoding="utf-8"), case_file.name)
        if not chunks:
            verdict, message = judge_unscored(expected)
            results.append(CaseResult(
                specialist=name, case_file=case_file.name, expected=expected,
                label="unscored", confidence=0.0, score=0.0,
                verdict=verdict, message=message,
            ))
            continue

        # Case score = worst (max) chunk score: any violating chunk fails a
        # clean case; any firing chunk carries a violation case.
        best_label, best_confidence, best_score = "negative", 0.0, -1.0
        for chunk in chunks:
            outcome = specialist.classify(chunk.text)
            score = violation_score(outcome["label"], outcome["confidence"])
            if score > best_score:
                best_label = outcome["label"]
                best_confidence = outcome["confidence"]
                best_score = score

        verdict, message = judge(expected, best_score)
        if len(chunks) > 1:
            note = f"{len(chunks)} chunks, max score shown"
            message = f"{message} [{note}]" if message else f"[{note}]"

        results.append(
            CaseResult(
                specialist=name,
                case_file=case_file.name,
                expected=expected,
                label=best_label,
                confidence=best_confidence,
                score=best_score,
                verdict=verdict,
                message=message,
            )
        )

    return results


def verify_composite(name: str, models_dir: Path, composite_cfg: dict) -> list[CaseResult]:
    """Verify a composite principle with the production pipeline: per chunk,
    trigger gate -> deterministic name exemption (or learned exemption
    specialist) -> violation specialist at the CrasisScorer confidence
    threshold (0.85, matching POS_THRESHOLD).
    """
    case_dir = CASES_DIR / name
    if not case_dir.is_dir():
        print(f"warning: no case directory for composite '{name}' at {case_dir}", file=sys.stderr)
        return []

    violation_name = str(composite_cfg["violation_specialist"])
    exemption_name = composite_cfg.get("exemption_specialist")
    exempt_names = set(composite_cfg.get("exemption_signatures") or [])
    trigger_patterns = [re.compile(p) for p in composite_cfg.get("trigger_patterns", [])]
    delegation_call_patterns = [re.compile(p) for p in composite_cfg.get("delegation_call_patterns", [])]
    cleared_value_patterns = list(composite_cfg.get("cleared_value_patterns", []))
    redact_for_violation = bool(composite_cfg.get("redact_for_violation", False))
    preserve_prefixes = tuple(composite_cfg.get("redaction_preserve_prefixes", []))

    from crasis import Specialist

    violation_model_dir = resolve_model_dir(models_dir, violation_name)
    if not violation_model_dir.is_dir():
        print(f"warning: missing model dir {violation_model_dir} for composite '{name}' — skipping", file=sys.stderr)
        return []
    violation_specialist = Specialist.load(violation_model_dir)

    exemption_specialist = None
    if exemption_name is not None:
        exemption_model_dir = resolve_model_dir(models_dir, str(exemption_name))
        if not exemption_model_dir.is_dir():
            print(f"warning: missing model dir {exemption_model_dir} for composite '{name}' — skipping", file=sys.stderr)
            return []
        exemption_specialist = Specialist.load(exemption_model_dir)

    results: list[CaseResult] = []
    case_files = sorted(case_dir.glob("*.cpp"))
    if not case_files:
        print(f"warning: no .cpp case files found in {case_dir}", file=sys.stderr)
        return []

    for case_file in case_files:
        expected = expected_from_filename(case_file)
        if expected is None:
            print(f"warning: skipping {case_file.name} — does not start with pos__ or neg__", file=sys.stderr)
            continue

        chunks = production_chunks(case_file.read_text(encoding="utf-8"), case_file.name)
        if not chunks:
            verdict, message = judge_unscored(expected)
            results.append(CaseResult(
                specialist=name, case_file=case_file.name, expected=expected,
                label="unscored", confidence=0.0, score=0.0,
                verdict=verdict, message=message,
            ))
            continue

        composite_positive = False
        confidence = 0.0
        details: list[str] = []
        for chunk in chunks:
            if trigger_patterns and not any(p.search(chunk.text) for p in trigger_patterns):
                details.append("gated-out (no trigger pattern)")
                continue
            if exempt_names and _method_name_from_signature(chunk.signature) in exempt_names:
                details.append(f"name-exempt ({_method_name_from_signature(chunk.signature)})")
                continue

            delegation_verdict = _delegation_call_verdict(chunk.text, delegation_call_patterns)
            if delegation_verdict is not None:
                details.append(
                    f"delegation-call-verdict={'positive' if delegation_verdict else 'negative'} "
                    "(no model call)"
                )
                if delegation_verdict:
                    composite_positive = True
                    confidence = max(confidence, 1.0)
                continue

            cleared_value_verdict = (
                _cleared_value_assignment_verdict(chunk.text, cleared_value_patterns)
                if cleared_value_patterns else None
            )
            if cleared_value_verdict is not None:
                # False is authoritative here (see crasis_scorer.py's
                # _cleared_value_assignment_verdict docstring): no direct
                # member assignment and no local-variable-laundering path for
                # the cleared value. A None verdict (laundering path present)
                # falls through to the model instead of hitting this branch.
                details.append(
                    f"cleared-value-verdict={'positive' if cleared_value_verdict else 'negative'} (no model call)"
                )
                if cleared_value_verdict:
                    composite_positive = True
                    confidence = max(confidence, 1.0)
                continue

            violation_text = (
                redact_identifiers(chunk.text, preserve_prefixes=preserve_prefixes)
                if redact_for_violation else chunk.text
            )
            v_outcome = violation_specialist.classify(violation_text)
            fires = v_outcome["label"] == "positive" and v_outcome["confidence"] >= POS_THRESHOLD
            detail = f"violation={v_outcome['label']}({v_outcome['confidence']:.4f})"

            if fires and exemption_specialist is not None:
                e_outcome = exemption_specialist.classify(chunk.text)
                exempt = e_outcome["label"] == "positive" and e_outcome["confidence"] >= POS_THRESHOLD
                detail += f" exemption={e_outcome['label']}({e_outcome['confidence']:.4f})"
                if exempt:
                    fires = False

            details.append(detail)
            if fires:
                composite_positive = True
                confidence = max(confidence, v_outcome["confidence"])

        # score is the number judge()/the report actually act on: 1.0 when the
        # composite fires on any chunk, 0.0 when it doesn't.
        label = "positive" if composite_positive else "negative"
        score = 1.0 if composite_positive else 0.0
        verdict, message = judge(expected, score)
        detail = "; ".join(details)
        message = f"{message} [{detail}]" if message else f"[{detail}]"

        results.append(
            CaseResult(
                specialist=name,
                case_file=case_file.name,
                expected=expected,
                label=label,
                confidence=confidence,
                score=score,
                verdict=verdict,
                message=message,
            )
        )

    return results


def write_report(
    all_results: dict[str, list[CaseResult]],
    models_dir: Path,
    mandatory: set[str],
) -> bool:
    """Write report.md; return True when no MANDATORY specialist has a failure.

    Non-mandatory specialists' failures are listed in full but marked
    non-blocking — they cannot block CONVERGED in the loop, so they do not
    block the verification gate either.
    """
    lines: list[str] = []
    lines.append("# Demo 8 BMS — Specialist Verification Report")
    lines.append("")
    lines.append(f"Models directory: `{models_dir}`")
    lines.append("")
    lines.append(
        f"Acceptance rule: violation cases must score above {POS_THRESHOLD}; "
        f"clean cases must score below {NEG_THRESHOLD}. A clean case scoring in "
        f"[{NEG_THRESHOLD}, {POS_THRESHOLD}) is a FAIL — add negatives and rebuild, "
        "no threshold tuning. Cases are routed through the production chunker; a "
        "case the chunker never scores (no function-level chunk) passes when clean "
        "and fails when it hides a violation. Failures of specialists not listed "
        "in the profile's mandatory_principles are reported but non-blocking, "
        "matching what non-mandatory means in the loop."
    )
    lines.append("")

    overall_pass = True

    for specialist, results in all_results.items():
        is_mandatory = specialist in mandatory
        lines.append(f"## {specialist}{'' if is_mandatory else ' (non-mandatory)'}")
        lines.append("")
        if not results:
            lines.append("_No cases run (missing model or case directory)._")
            lines.append("")
            continue

        lines.append("| Case | Expected | Label | Confidence | Score | Verdict | Note |")
        lines.append("|---|---|---|---|---|---|---|")
        n_pass = 0
        for r in results:
            if r.verdict != "PASS":
                if is_mandatory:
                    overall_pass = False
            else:
                n_pass += 1
            lines.append(
                f"| `{r.case_file}` | {r.expected} | {r.label} | {r.confidence:.4f} | "
                f"{r.score:.4f} | {r.verdict} | {r.message} |"
            )
        lines.append("")
        summary = f"**Summary: {n_pass}/{len(results)} cases passed.**"
        if not is_mandatory and n_pass < len(results):
            summary += " _(failures non-blocking: not in mandatory_principles)_"
        lines.append(summary)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Overall result: {'PASS' if overall_pass else 'FAIL'}**")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return overall_pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        dest="only",
        help="Verify only this specialist (repeatable). Default: all specialists with a case directory.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help=f"Directory containing <specialist>-onnx model exports (default: {DEFAULT_MODELS_DIR})",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help=f"Profile TOML providing [scorers.crasis.composites] (default: {DEFAULT_PROFILE})",
    )
    args = parser.parse_args()

    composites, mandatory = load_crasis_config(args.profile)

    if args.only:
        specialist_names = args.only
    else:
        specialist_names = sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())

    all_results: dict[str, list[CaseResult]] = {}
    any_ran = False

    for name in specialist_names:
        if name in composites:
            results = verify_composite(name, args.models_dir, composites[name])
        else:
            results = verify_specialist(name, args.models_dir)
        all_results[name] = results
        if results:
            any_ran = True
        for r in results:
            print(f"[{r.verdict}] {name}/{r.case_file}: expected={r.expected} label={r.label} "
                  f"confidence={r.confidence:.4f} score={r.score:.4f} {r.message}")

    overall_ok = write_report(all_results, args.models_dir, mandatory)
    print(f"\nReport written to {REPORT_PATH}")

    if not any_ran:
        print("no cases were run — check --models-dir and case directories", file=sys.stderr)
        return 2

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
