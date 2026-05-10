# Smelt Demo 2 — Black Box Generation

Demo 1 converged in one iteration. That sounds like success. It wasn't.

The generator was given the frozen test source in its prompt. It read the
assertions and implemented against them directly. Correct by inspection,
not correct by design. The loop did no real work.

Demo 2 fixes the architecture. The generator sees the spec, the test goals,
and the test function signatures — never the test assertions. Convergence
is driven entirely by failure detail from the runner and scorer.

This is how the loop is supposed to work.

---

## The Architectural Fix

**Demo 1 prompt (broken):**
```
SPEC:
{spec}

FROZEN TESTS (read-only reference):
{full test source including all assertions}

Generate the implementation.
```

**Demo 2 prompt (correct):**
```
SPEC:
{spec}

TEST GOALS (what the tests verify — not the test code):
{goals}

TEST FUNCTION SIGNATURES (names only — you cannot see the assertions):
test_addition(self)
test_subtraction(self)
test_multiplication_before_addition(self)
...

ITERATION: {n}
{failure detail from previous iteration, or "First attempt" on iteration 1}
```

The generator never sees test source. It sees the spec, the goals, the function
names, and — after the first iteration — exactly what failed and why. Convergence
is earned by fixing real failures, not by reading the answers.

A hard guard enforces this: before every API call, `_assert_no_test_source()`
runs a 10-word sliding window match between the prompt and the frozen test file.
If any window matches, the run aborts with an explicit error. Non-negotiable
by construction.

---

## Why Demo 1 Converged in One Iteration

When the generator sees the full test source, it does not solve the problem
from the spec. It reads the assertions and inverts them into an implementation.

For the rate limiter, the test file contained assertions like:
```python
assert limiter.acquire(1) == True
assert limiter.tokens == burst - 1
```

The generator could read `.tokens` was the state field, `acquire()` returned
a bool, and the exact arithmetic relationship between tokens and burst. It did
not derive these from the spec — it copied them from the test.

This produces code that is correct-by-inspection. The loop ran once, scored
1.0, and stopped. That is not convergence. That is reading the answer key.

---

## Demo 2 Target: Recursive Descent Expression Parser

A recursive descent parser for arithmetic expressions was chosen because:

- Operator precedence is a well-known failure mode for first-pass generation
- Multiple interacting grammar rules create non-trivial failure modes
- Docstring and type annotation compliance is reliably absent on first pass
- The implementation is complex enough to produce real compliance violations

**Compliance scorers:** ruff (E, F, W, I, D, ANN rules) weighted 0.4 + mypy
--strict weighted 0.6. Thresholds: compliance >= 0.95, goal = 1.00 (all tests pass).

---

## Run: 20260510_001122

### Convergence Table

| Iter | ruff  | mypy  | weighted | goal  | composite | Status |
|------|-------|-------|----------|-------|-----------|--------|
| 1    | 0.653 | 1.000 | 0.861    | 1.000 | 0.861     | below threshold |
| 2    | 0.259 | 0.996 | 0.701    | 0.000 | 0.000     | malformed output |
| 3    | 0.667 | 0.897 | 0.805    | 1.000 | 0.805     | below threshold |
| 4    | 0.992 | 1.000 | 0.997    | 1.000 | 0.997     | **CONVERGED** |

### Iteration 1

**Generated:** A working parser, all 60+ tests pass. But 42 ruff violations:
missing module docstring, missing class docstrings, missing method docstrings
(D100, D101, D102, D107), missing type annotations on `__init__` (ANN204).

**Weighted compliance: 0.861** — below the 0.95 threshold. Loop continues.

**Reprompt includes:**
```
COMPLIANCE FAILURES:
  ruff  D100  line 1  Missing docstring in public module
  ruff  D101  line 1  Missing docstring in public class
  ruff  D101  line 5  Missing docstring in public class
  ruff  ANN204  line 6  Missing return type annotation for special method `__init__`
  ruff  D107  line 6  Missing docstring in `__init__`
  ... and 37 more
```

### Iteration 2

**Generated:** The LLM included markdown code fences in its response
(backtick delimiters leaked into the output file). Ruff reported 192
`invalid-syntax` violations. Pytest could not import the module — 0 tests
passed, composite 0.0.

**This is a real failure that the loop handled correctly.** The reprompt
included the syntax errors and zero goal score, forcing a clean regeneration.

### Iteration 3

**Generated:** Clean Python, all tests pass again. 39 ruff violations
(docstrings still incomplete) and 12 mypy violations (missing return type
annotations on internal helper methods). Weighted compliance: 0.805.

**Reprompt includes both scorer failure streams:**
```
COMPLIANCE FAILURES:
  ruff  D102  line 21  Missing docstring in public method
  mypy  [no-untyped-def]  line 21  Function is missing a return type annotation
  ... 49 more
```

### Iteration 4 — CONVERGED

**Generated:** Full docstrings on all public classes and methods, type
annotations on all functions. One remaining ruff E501 (line too long, 107 > 88)
too minor to drop compliance below 0.95. Final scores:

- ruff: 0.992 (1 violation remaining)
- mypy: 1.000 (clean)
- weighted compliance: 0.997
- goal: 1.000 (all tests pass)
- **composite: 0.997**

---

## Final Implementation

```python
"""Expression parser module implementing recursive descent parsing."""


class ParseError(Exception):
    """Exception raised for parsing errors."""

    def __init__(self, message: str) -> None:
        """Initialize ParseError with a message."""
        self.message = message
        super().__init__(self.message)


class Parser:
    """Recursive descent parser for arithmetic expressions."""

    def __init__(self, expression: str) -> None:
        """Initialize the parser with an expression string."""
        self.expression = expression
        self.pos = 0
        self.skip_whitespace()

    def skip_whitespace(self) -> None:
        """Skip whitespace characters in the expression."""
        while self.pos < len(self.expression) and self.expression[self.pos].isspace():
            self.pos += 1

    def peek(self) -> str | None:
        """Peek at the current character without consuming it."""
        self.skip_whitespace()
        if self.pos < len(self.expression):
            return self.expression[self.pos]
        return None

    def consume(self, expected: str | None = None) -> str:
        """Consume and return the current character."""
        self.skip_whitespace()
        if self.pos >= len(self.expression):
            if expected:
                raise ParseError(f"Expected '{expected}' but reached end of expression")
            raise ParseError("Unexpected end of expression")
        char = self.expression[self.pos]
        if expected and char != expected:
            raise ParseError(f"Expected '{expected}' but got '{char}'")
        self.pos += 1
        return char

    def parse_number(self) -> float:
        """Parse a number (integer or float)."""
        self.skip_whitespace()
        start = self.pos
        has_dot = False

        while self.pos < len(self.expression):
            char = self.expression[self.pos]
            if char.isdigit():
                self.pos += 1
            elif char == '.' and not has_dot:
                has_dot = True
                self.pos += 1
            else:
                break

        if start == self.pos:
            raise ParseError("Expected number")

        num_str = self.expression[start:self.pos]
        if num_str == '.':
            raise ParseError("Invalid number")
        if num_str.count('.') > 1:
            raise ParseError("Invalid number: multiple decimal points")

        return float(num_str)

    def parse_primary(self) -> float:
        """Parse a primary expression (number or parenthesized expression)."""
        self.skip_whitespace()
        char = self.peek()

        if char is None:
            raise ParseError("Unexpected end of expression")

        if char == '(':
            self.consume('(')
            if self.peek() == ')':
                raise ParseError("Empty parentheses")
            result = self.parse_expr()
            self.consume(')')
            return result
        elif char.isdigit() or char == '.':
            return self.parse_number()
        else:
            raise ParseError(f"Unexpected character: '{char}'")

    def parse_unary(self) -> float:
        """Parse a unary expression (optional minus sign)."""
        self.skip_whitespace()
        char = self.peek()

        if char == '-':
            self.consume('-')
            return -self.parse_unary()
        else:
            return self.parse_primary()

    def parse_factor(self) -> float:
        """Parse a factor (unary or primary)."""
        return self.parse_unary()

    def parse_term(self) -> float:
        """Parse a term (multiplication and division)."""
        self.skip_whitespace()
        result = self.parse_factor()

        while True:
            self.skip_whitespace()
            char = self.peek()

            if char == '*':
                self.consume('*')
                result *= self.parse_factor()
            elif char == '/':
                self.consume('/')
                divisor = self.parse_factor()
                if divisor == 0:
                    raise ZeroDivisionError("Division by zero")
                result /= divisor
            else:
                break

        return result

    def parse_expr(self) -> float:
        """Parse an expression (addition and subtraction)."""
        self.skip_whitespace()
        result = self.parse_term()

        while True:
            self.skip_whitespace()
            char = self.peek()

            if char == '+':
                self.consume('+')
                result += self.parse_term()
            elif char == '-':
                self.consume('-')
                result -= self.parse_term()
            else:
                break

        return result


def parse(expression: str) -> float:
    """Parse and evaluate an arithmetic expression."""
    if not expression or not expression.strip():
        raise ParseError("Empty expression")

    parser = Parser(expression)
    result = parser.parse_expr()

    parser.skip_whitespace()
    if parser.pos < len(parser.expression):
        raise ParseError(f"Unexpected character: '{parser.expression[parser.pos]}'")

    return result
```

---

## What Changed

**Rule 7 is the governing invariant:** The Phase 2 generation prompt never
contains test source code — ever. Not the assertions. Not the imports. Not
the fixture setup. Nothing from the frozen test file beyond function signatures.

The generator sees exactly what a developer sees before a test suite exists:
the requirements and the names of what needs to be verified. It does not see
how the tests verify it.

The loop drives convergence through failure detail alone:
- Compliance: rule ID, file, line, message for every violation
- Goal: failing test names, expected vs actual, truncated traceback

The generator learns what broke and what was expected. It never learns how
the test is written. This is the black box guarantee.

**Demo 1** produced correct-by-inspection code in one iteration.
**Demo 2** produced correct-by-design code in four iterations, with visible
failure-driven convergence at every step.

The loop is the product. Demo 2 shows it working.
