"""Verify generated test arithmetic against formulas stated in the spec.

Phase 1's test generator computes expected values for integer-arithmetic
conversions by hand (e.g. "raw ADC count 3277 converts to how many
millivolts?") when the spec doesn't already provide a worked example for
that exact input. This is unreliable — an LLM asked to mentally compute
`(3277 * 5000) // 4095` has no way to check its own arithmetic, and a wrong
literal baked into a frozen test is unfixable by Phase 2 (the generator can
never modify frozen tests, so no implementation can ever satisfy a wrong
assertion).

This module extracts backtick-quoted single-expression formulas from the
spec (the convention used throughout demo/bms/bms_spec.md, e.g.
`` `(raw_counts * 5000) / 4095` ``), evaluates them with a restricted,
safe arithmetic parser, and cross-checks them against numeric literals in
the generated test that were plausibly derived from a `configure(...)` call
feeding the same input into a formula's variable.

This is intentionally narrow: it only catches "formula applied to a
concrete input literal" mismatches, which is exactly the failure mode
observed (see `demo/bms/verification/diagnosis.md` sibling investigations
for how the same category of narrow-check-vs-broad-check tradeoff played
out for the crasis specialists). It does not attempt to verify arbitrary
test logic.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass

_FORMULA_PATTERN = re.compile(r"`([^`]*[a-zA-Z_]\w*[^`]*[-+*/][^`]*)`")

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Div: operator.floordiv,  # spec formulas use integer division throughout
}
_ALLOWED_UNARYOPS = {
    ast.USub: operator.neg,
}


@dataclass(frozen=True)
class Formula:
    """A single-variable integer arithmetic formula extracted from the spec."""

    source: str
    var_name: str
    expr: ast.expr

    def evaluate(self, value: int) -> int:
        return _eval_restricted(self.expr, {self.var_name: value})


class UnsafeExpressionError(ValueError):
    """Raised when a spec formula contains a construct outside the allowed grammar."""


def _eval_restricted(node: ast.expr, env: dict[str, int]) -> int:
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_restricted(node.left, env)
        right = _eval_restricted(node.right, env)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_restricted(node.operand, env))
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    raise UnsafeExpressionError(f"Disallowed expression node: {ast.dump(node)}")


_CONSTANT_NAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*\b")


def extract_formulas(spec_text: str) -> list[Formula]:
    """Find backtick-quoted arithmetic formulas with exactly one free variable.

    Only formulas of the shape `expr_using_one_variable` are kept — anything
    with zero or more than one distinct identifier is skipped as ambiguous
    (e.g. a formula referencing two different raw counts can't be checked
    against a single configure() literal without knowing which is which).

    Formulas whose sole variable is an ALL_CAPS identifier are also skipped:
    that naming convention is used throughout the spec for named constants
    (CELL_COUNT, ADC_MAX_COUNTS, ...), not per-call inputs like raw_counts —
    treating a constant as a free variable produces false-positive
    "mismatches" against unrelated numeric literals elsewhere in the test.
    """
    formulas: list[Formula] = []
    for match in _FORMULA_PATTERN.finditer(spec_text):
        candidate = match.group(1).strip()

        # Accept both `expr` and `out_var = expr` forms — the spec convention
        # uses whichever reads more naturally in prose (assignment form in
        # narrative text, bare expression form in the per-method reference).
        rhs = candidate
        if "=" in candidate and "==" not in candidate:
            _, _, rhs = candidate.partition("=")
            rhs = rhs.strip()

        try:
            tree = ast.parse(rhs, mode="eval").body
        except SyntaxError:
            continue

        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        if len(names) != 1:
            continue
        var_name = next(iter(names))
        if _CONSTANT_NAME_PATTERN.fullmatch(var_name):
            continue

        try:
            _eval_restricted(tree, {var_name: 0})
        except UnsafeExpressionError:
            continue

        formulas.append(Formula(source=candidate, var_name=var_name, expr=tree))
    return formulas


@dataclass(frozen=True)
class ArithmeticMismatch:
    formula: str
    input_value: int
    expected_by_formula: int
    asserted_in_test: int
    context: str


def check_test_arithmetic(test_source: str, formulas: list[Formula]) -> list[ArithmeticMismatch]:
    """Cross-check EXPECT_EQ literals against configure()-fed formula inputs.

    Heuristic, deliberately conservative: within each TEST(...) { ... } block,
    find every `configure(<args>)` call's integer-literal arguments, then for
    every `EXPECT_EQ(<literal>, ...)` in the same block, check whether any
    formula applied to any of those configure literals would have produced a
    different integer than the asserted literal. A mismatch is only reported
    when the asserted literal exactly equals neither the correct formula
    result nor is otherwise explained — floods of false positives are worse
    than a missed catch here, so ambiguous cases are skipped rather than
    flagged.
    """
    mismatches: list[ArithmeticMismatch] = []
    if not formulas:
        return mismatches

    for test_match in re.finditer(r"TEST(?:_F)?\([^)]*\)\s*\{(.*?)\n\}", test_source, re.DOTALL):
        block = test_match.group(1)

        configure_literals: set[int] = set()
        for call_match in re.finditer(r"\.configure\(([^;]*?)\);", block):
            args = call_match.group(1)
            configure_literals.update(
                int(lit) for lit in re.findall(r"-?\d+", args)
            )
        if not configure_literals:
            continue

        for expect_match in re.finditer(r"EXPECT_EQ\((-?\d+),\s*([^)]+)\)", block):
            asserted = int(expect_match.group(1))
            for raw_input in configure_literals:
                for formula in formulas:
                    try:
                        correct = formula.evaluate(raw_input)
                    except Exception:
                        continue
                    # Only flag when this raw input, run through this formula,
                    # produces a value close to (but not equal to) what was
                    # asserted — this is the "off by a small rounding slip"
                    # signature, not a coincidental unrelated literal match.
                    if correct != asserted and abs(correct - asserted) <= 2:
                        mismatches.append(
                            ArithmeticMismatch(
                                formula=formula.source,
                                input_value=raw_input,
                                expected_by_formula=correct,
                                asserted_in_test=asserted,
                                context=test_match.group(0)[:200],
                            )
                        )
    return mismatches
