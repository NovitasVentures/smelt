#!/usr/bin/env python3
"""Verification harness for Demo 8 BMS Crasis specialists.

Runs every case file in cases/<specialist>/{pos,neg}__*.cpp through the
matching ONNX specialist model and checks it against the acceptance rule in
demo/bms/specialist_authoring.md Step 3:

    - positive (violation) cases must score above 0.85
    - negative (clean) cases must score below 0.80
    - a negative in [0.80, 0.85) is a FAIL: "add negatives and rebuild --
      no threshold tuning" (there is no fixup available for a reused model)

The "score" reported here is a single violation-likelihood number in [0, 1],
derived from the specialist's raw (label, confidence) output:

    score = confidence            if label == "positive"
    score = 1 - confidence        if label == "negative"

This makes the 0.85 / 0.80 thresholds directly comparable regardless of which
class the model actually predicted.

Usage:
    python3 verify.py                       # verify every specialist with a model present
    python3 verify.py --only <specialist>   # verify a single specialist
    python3 verify.py --models-dir <path>   # override the default models directory

Exit code is nonzero if any case fails.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from smelt.scorers.chunker import redact_identifiers

VERIFICATION_DIR = Path(__file__).resolve().parent
CASES_DIR = VERIFICATION_DIR / "cases"
DEFAULT_MODELS_DIR = VERIFICATION_DIR.parent / "specialists"
REPORT_PATH = VERIFICATION_DIR / "report.md"

POS_THRESHOLD = 0.85  # violation cases must score strictly above this
NEG_THRESHOLD = 0.80  # clean cases must score strictly below this

# Maps specialist name -> subdirectory layout under --models-dir, matching
# the nested export structure crasis arch-build produces:
#   <models-dir>/<specialist>-onnx/<specialist>-onnx/
MODEL_SUBPATH = "{name}-onnx/{name}-onnx"

# Composite principles: a chunk violates COMPOSITE iff violation_specialist fires
# positive AND exemption_specialist does not. Cases under cases/<composite_name>/
# are verified using both underlying specialists rather than a single model dir.
# Keep in sync with [scorers.crasis.composites] in the active TOML profile.
COMPOSITES: dict[str, dict[str, object]] = {
    "fault-cleared-outside-reset": {
        "violation_specialist": "fault-clearing-dataflow",
        "exemption_specialist": "reset-name-exemption",
        "redact_for_violation": True,
    },
}


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


def resolve_model_dir(models_dir: Path, specialist: str) -> Path:
    return models_dir / MODEL_SUBPATH.format(name=specialist)


def expected_from_filename(path: Path) -> str | None:
    stem = path.name
    if stem.startswith("pos__"):
        return "positive"
    if stem.startswith("neg__"):
        return "negative"
    return None


def strip_leading_comments(text: str) -> str:
    """Drop leading '//'-only lines and blank lines.

    Case files carry an authoring comment above the function body for human
    readability (which shape/method it represents), but smelt/scorers/chunker.py
    anchors its function-header regex with `^(?![ \\t]*//)` — a chunk's text
    always starts at the signature line, never at a preceding comment. Feeding
    the model text it would never see in production understates (or skews)
    its real accuracy, so this strips exactly what the chunker would exclude.
    """
    lines = text.splitlines()
    start = 0
    while start < len(lines) and (not lines[start].strip() or lines[start].strip().startswith("//")):
        start += 1
    return "\n".join(lines[start:])


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

        text = strip_leading_comments(case_file.read_text(encoding="utf-8"))
        outcome = specialist.classify(text)
        score = violation_score(outcome["label"], outcome["confidence"])
        verdict, message = judge(expected, score)

        results.append(
            CaseResult(
                specialist=name,
                case_file=case_file.name,
                expected=expected,
                label=outcome["label"],
                confidence=outcome["confidence"],
                score=score,
                verdict=verdict,
                message=message,
            )
        )

    return results


def verify_composite(name: str, models_dir: Path) -> list[CaseResult]:
    """Verify a composite principle: violation iff violation_specialist fires
    positive AND exemption_specialist does not fire positive, both at the
    confidence_threshold used by CrasisScorer (0.85, matching POS_THRESHOLD).
    """
    case_dir = CASES_DIR / name
    if not case_dir.is_dir():
        print(f"warning: no case directory for composite '{name}' at {case_dir}", file=sys.stderr)
        return []

    composite_cfg = COMPOSITES[name]
    violation_name = str(composite_cfg["violation_specialist"])
    exemption_name = str(composite_cfg["exemption_specialist"])
    redact_for_violation = bool(composite_cfg["redact_for_violation"])

    violation_model_dir = resolve_model_dir(models_dir, violation_name)
    exemption_model_dir = resolve_model_dir(models_dir, exemption_name)
    if not violation_model_dir.is_dir() or not exemption_model_dir.is_dir():
        print(
            f"warning: missing model dir for composite '{name}' "
            f"(violation={violation_model_dir}, exemption={exemption_model_dir}) — skipping",
            file=sys.stderr,
        )
        return []

    from crasis import Specialist

    violation_specialist = Specialist.load(violation_model_dir)
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

        text = strip_leading_comments(case_file.read_text(encoding="utf-8"))
        violation_text = redact_identifiers(text) if redact_for_violation else text

        v_outcome = violation_specialist.classify(violation_text)
        e_outcome = exemption_specialist.classify(text)

        fires = v_outcome["label"] == "positive" and v_outcome["confidence"] >= POS_THRESHOLD
        exempt = e_outcome["label"] == "positive" and e_outcome["confidence"] >= POS_THRESHOLD
        composite_positive = fires and not exempt

        # score is the number judge()/the report actually act on: 1.0 when the
        # composite fires (both conditions hold), 0.0 when it doesn't. label is
        # kept only for the report table; it mirrors composite_positive.
        label = "positive" if composite_positive else "negative"
        score = 1.0 if composite_positive else 0.0
        confidence = v_outcome["confidence"] if composite_positive else e_outcome["confidence"]
        verdict, message = judge(expected, score)
        detail = (
            f"violation={v_outcome['label']}({v_outcome['confidence']:.4f}) "
            f"exemption={e_outcome['label']}({e_outcome['confidence']:.4f})"
        )
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


def write_report(all_results: dict[str, list[CaseResult]], models_dir: Path) -> None:
    lines: list[str] = []
    lines.append("# Demo 8 BMS — Specialist Verification Report")
    lines.append("")
    lines.append(f"Models directory: `{models_dir}`")
    lines.append("")
    lines.append(
        f"Acceptance rule: violation cases must score above {POS_THRESHOLD}; "
        f"clean cases must score below {NEG_THRESHOLD}. A clean case scoring in "
        f"[{NEG_THRESHOLD}, {POS_THRESHOLD}) is a FAIL — add negatives and rebuild, "
        "no threshold tuning."
    )
    lines.append("")

    overall_pass = True

    for specialist, results in all_results.items():
        lines.append(f"## {specialist}")
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
                overall_pass = False
            else:
                n_pass += 1
            lines.append(
                f"| `{r.case_file}` | {r.expected} | {r.label} | {r.confidence:.4f} | "
                f"{r.score:.4f} | {r.verdict} | {r.message} |"
            )
        lines.append("")
        lines.append(f"**Summary: {n_pass}/{len(results)} cases passed.**")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Overall result: {'PASS' if overall_pass else 'FAIL'}**")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


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
    args = parser.parse_args()

    if args.only:
        specialist_names = args.only
    else:
        specialist_names = sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())

    all_results: dict[str, list[CaseResult]] = {}
    any_ran = False
    overall_ok = True

    for name in specialist_names:
        if name in COMPOSITES:
            results = verify_composite(name, args.models_dir)
        else:
            results = verify_specialist(name, args.models_dir)
        all_results[name] = results
        if results:
            any_ran = True
        for r in results:
            print(f"[{r.verdict}] {name}/{r.case_file}: expected={r.expected} label={r.label} "
                  f"confidence={r.confidence:.4f} score={r.score:.4f} {r.message}")
            if r.verdict != "PASS":
                overall_ok = False

    write_report(all_results, args.models_dir)
    print(f"\nReport written to {REPORT_PATH}")

    if not any_ran:
        print("no cases were run — check --models-dir and case directories", file=sys.stderr)
        return 2

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
