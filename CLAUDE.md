# Smelt — CLAUDE.md

**https://runsmelt.dev** · MIT License · FOSS

Smelt is a spec-driven autonomous code generation system. It takes a natural language
spec, a set of test goals, and a standards profile, then loops — generating code,
scoring it against frozen tests and compliance rules, and reprompting with failure
detail — until the code converges to a passing, compliant state.

The loop is the product. The scorer is pluggable. The tests are immutable once frozen.

---

## Architecture

```
smelt/
├── core/
│   ├── loop.py          # Main generation/score/reprompt loop
│   ├── phase1.py        # Test synthesis and mutation gating
│   ├── phase2.py        # Code generation loop
│   └── scorer.py        # Composite score: compliance × goal
├── scorers/
│   ├── base.py          # Scorer interface (all scorers implement this)
│   ├── ruff_scorer.py
│   ├── black_scorer.py
│   ├── pylint_scorer.py
│   ├── clang_tidy_scorer.py
│   ├── misra_scorer.py
│   ├── autosar_scorer.py
│   └── crasis_scorer.py  # Stub — semantic/architectural scorer (roadmap)
├── runners/
│   ├── base.py           # Test runner interface
│   ├── pytest_runner.py
│   └── gtest_runner.py
├── mutator/
│   └── mutation_gate.py  # mutmut (Python) or mutate++ (C/C++) integration
├── llm/
│   └── client.py         # LLM interface — defaults to Claude API
├── config/
│   └── profiles/
│       ├── python_default.toml
│       ├── c_misra.toml
│       └── cpp_autosar.toml
└── cli.py               # Entry point
```

### Core Loop Invariants

These must never be violated regardless of language or standards profile:

1. **Tests are frozen after Phase 1.** The code generator has no write access to test
   files. Ever. The only exit from the loop is making the implementation pass the
   frozen tests.

2. **Score = compliance_score × goal_score.** Both are normalized 0.0–1.0. Neither
   can compensate for the other — a 1.0 compliance with 0.0 goal is 0.0. Both must
   converge.

3. **Failure detail is always specific.** Reprompt payloads must include exact failure
   messages, line numbers, rule identifiers, and test names. Never reprompt with only
   a score — always include why.

4. **Iteration trace is always written.** Every cycle writes to the trace log:
   iteration number, compliance score, goal score, composite score, failure summary.
   This is non-negotiable — it's the proof of convergence.

---

## Phase 1 — Test Synthesis

Phase 1 generates a test suite from the spec and test goals, then validates that
the test suite is non-trivial before freezing it.

**Mutation gate:** Before freezing, run the mutation engine against a stub
implementation. Minimum kill rate is defined in the profile (default: 0.70). If
the generated tests don't kill 70% of mutations, regenerate. This prevents the
LLM from producing tests that any implementation would pass.

**Frozen test storage:** Write tests to `smelt_output/frozen_tests/` with a
content hash recorded in `smelt_output/manifest.json`. The loop verifier checks
this hash before every iteration. If tests have been modified, the run aborts.

---

## Phase 2 — Code Generation Loop

The loop reprompts with:
- The original spec (always included)
- The frozen test file paths (read-only reference)
- Current iteration number and score history
- Specific failure detail from this iteration:
  - Compliance: rule ID, file, line, message for every violation
  - Goal: failing test names, assertion messages, coverage gaps if available
- Instruction to fix failures without modifying tests

Exit conditions (both must be satisfied, OR iteration cap hit):
- compliance_score >= profile threshold (default: 0.95)
- goal_score >= profile threshold (default: 1.00 — all tests pass)

On iteration cap: write final state, mark run as UNCONVERGED, surface last score.

---

## Standards Profiles

Profiles live in `smelt/config/profiles/` as TOML files. The active profile is
set in `smelt.toml` at the repo root or passed via `--profile` flag.

### Profile Schema

```toml
[meta]
name        = "python_default"
language    = "python"
version     = "1.0"

[thresholds]
compliance  = 0.95   # minimum compliance_score to exit
goal        = 1.00   # minimum goal_score to exit
mutation    = 0.70   # minimum mutation kill rate to freeze tests

[iterations]
max         = 20     # hard cap before UNCONVERGED

[scorers]
# List in priority order. All run each iteration.
active      = ["black", "ruff"]

[runners]
framework   = "pytest"

[mutator]
engine      = "mutmut"
```

---

## Profile 1 — Python / Black / Pytest (Default)

**File:** `smelt/config/profiles/python_default.toml`

```toml
[meta]
name     = "python_default"
language = "python"

[scorers]
active   = ["black", "ruff"]

[runners]
framework = "pytest"
coverage  = true          # collect pytest-cov, report branch coverage

[mutator]
engine    = "mutmut"
```

### Coding Conventions

When generating or modifying Python code under this profile:

- Format with `black` — 88 char line length, double quotes, no trailing commas
  in function signatures unless multi-line
- Lint with `ruff` — default ruleset plus `E`, `F`, `W`, `I` (isort)
- Type hints required on all public functions and methods
- Docstrings required on all public functions, classes, and modules
  (Google style)
- No `print()` in library code — use `logging`
- No bare `except:` — always catch specific exception types

### Test Conventions (pytest)

- Test files: `test_*.py` in `tests/` directory
- One test file per source module
- Fixtures in `conftest.py`
- Parametrize over input variations rather than writing repeated test functions
- Test names: `test_<function>_<scenario>_<expected_outcome>`
- Every public function must have at least one test for the happy path and one
  for a boundary or error condition
- Use `pytest.raises` for exception assertions — not try/except in tests

### Compliance Scorer — Python

The black scorer returns 1.0 if `black --check` exits 0, else 0.0 (binary).
The ruff scorer returns `1.0 - (violations / lines_of_code)` normalized and
clamped to [0.0, 1.0].

Composite compliance = mean(black_score, ruff_score).

---

## Profile 2 — Configurable Standards / Configurable Test Environment

**File:** `smelt/config/profiles/<custom>.toml`

Any profile can override any field from the default. Minimum required fields
are `meta.language` and `scorers.active`.

### Swapping the Linter

```toml
[scorers]
active = ["pylint"]

[scorers.pylint]
rcfile = ".pylintrc"       # path to pylintrc relative to project root
fail_under = 8.0           # pylint score threshold (0-10)
```

### Swapping the Test Framework

```toml
[runners]
framework = "unittest"     # pytest | unittest | gtest | catch2
```

### Adjusting Thresholds

```toml
[thresholds]
compliance = 0.80          # loosen for exploratory work
goal       = 0.90          # allow some test failures during early iterations
mutation   = 0.60          # loosen mutation gate for simple utility code
```

### Multi-scorer Weighting

When multiple scorers are active, weights can be assigned:

```toml
[scorers]
active  = ["ruff", "pylint"]
weights = { ruff = 0.4, pylint = 0.6 }
```

Unweighted scorers default to equal weighting.

---

## Profile 3 — C / MISRA / GTest

**File:** `smelt/config/profiles/c_misra.toml`

```toml
[meta]
name     = "c_misra"
language = "c"

[scorers]
active   = ["clang_tidy", "misra"]

[scorers.clang_tidy]
config   = ".clang-tidy"   # project clang-tidy config
checks   = "misra-*,cert-*,bugprone-*"

[scorers.misra]
ruleset  = "misra_c_2012"  # misra_c_2012 | misra_c_2023
tool     = "cppcheck"      # cppcheck | polyspace | pc-lint (must be on PATH)
required = true            # mandatory violations block exit regardless of score

[runners]
framework = "gtest"
build     = "cmake"        # cmake | make | ninja
build_dir = "build/"

[mutator]
engine    = "mutate++"     # C/C++ mutation engine

[thresholds]
compliance = 0.95
goal       = 1.00
mutation   = 0.70
```

### Coding Conventions — C/MISRA

When generating or modifying C code under this profile:

- Target C99 unless the profile specifies otherwise
- All MISRA C:2012 mandatory rules are hard stops — the loop will not exit with
  any mandatory violation regardless of score
- MISRA C:2012 required rules count against the compliance score
- Prohibited constructs: dynamic memory allocation (`malloc`/`free`),
  recursion, `goto`, `setjmp`/`longjmp`, multiple return points per function
  (advisory — flag but do not hard-stop)
- All variables declared at the top of their scope block
- No implicit function declarations — all functions declared before use
- Integer types: use `stdint.h` fixed-width types (`uint32_t` etc.) not bare
  `int` for anything where size matters
- Every switch statement has a `default` case
- No dead code — unreachable branches are MISRA violations

### Test Conventions — GTest with C Wrapper

GTest is C++ but testing C code. The generated test harness must:

- Wrap C code in `extern "C"` blocks
- One `TEST()` per logical behavior, not per function
- Use `ASSERT_*` for preconditions that make further testing meaningless
- Use `EXPECT_*` for all other assertions (allows test to continue on failure)
- Name pattern: `TEST(ModuleName, FunctionName_Scenario_ExpectedOutcome)`
- No test-to-test dependencies — every test must be runnable in isolation
- GTest XML output enabled: `--gtest_output=xml:smelt_output/test_results.xml`

### MISRA Scorer

The MISRA scorer wraps the configured static analysis tool and parses its output.

Compliance score calculation:
- Mandatory violations: each one applies a 0.20 penalty (hard, stackable to 0.0)
- Required violations: `1.0 - (required_count / total_rules_checked)`
- Advisory violations: reported in trace but do not affect score

The reprompt payload for MISRA failures must include:
- Rule ID (e.g. `MISRA C:2012 Rule 15.5`)
- Rule description
- File, line, column
- Violation severity (mandatory/required/advisory)

---

## Profile 4 — C++ / AUTOSAR / GTest

**File:** `smelt/config/profiles/cpp_autosar.toml`

```toml
[meta]
name     = "cpp_autosar"
language = "cpp"
std      = "c++14"         # AUTOSAR targets C++14

[scorers]
active   = ["clang_tidy", "autosar"]

[scorers.clang_tidy]
config   = ".clang-tidy"
checks   = "autosar-*,cppcoreguidelines-*,modernize-*,readability-*"

[scorers.autosar]
ruleset  = "autosar_cpp14"
tool     = "cppcheck"      # or polyspace, axivion, parasoft
required = true

[runners]
framework  = "gtest"
build      = "cmake"
build_dir  = "build/"
std        = "c++14"

[mutator]
engine     = "mutate++"

[thresholds]
compliance = 0.95
goal       = 1.00
mutation   = 0.70
```

### Coding Conventions — C++/AUTOSAR

AUTOSAR C++14 is a subset of C++14. When generating or modifying C++ code under
this profile:

- Target C++14 strictly — no C++17 or C++20 features
- No exceptions (`-fno-exceptions`) — error handling via return codes or
  `std::expected`-style wrappers
- No RTTI (`-fno-rtti`)
- No dynamic memory allocation after initialization phase — no `new`/`delete`
  in operational code paths
- No virtual functions in safety-critical paths (advisory — flag)
- All raw pointers must be justified — prefer references or smart pointers
  where ownership semantics apply
- `nullptr` not `NULL` not `0` for null pointers
- `static_assert` for compile-time invariants
- `constexpr` wherever values are known at compile time
- Scoped enums (`enum class`) — never unscoped enums
- No C-style casts — use `static_cast`, `reinterpret_cast` with explicit
  justification comment
- `[[nodiscard]]` on all functions returning error codes or resource handles
- No `using namespace` in headers — ever

### AUTOSAR Rules Commonly Triggered

These are the rules most likely to appear in failure reprompts. Generating code
that preemptively satisfies them reduces iteration count:

- **A5-1-1**: Literal values shall not be used outside of type initialization —
  use named constants
- **A7-1-1**: Constexpr or const specifier shall be used for immutable data
- **A8-4-7**: `in` parameters for cheap-to-copy types shall be passed by value
- **A15-5-1**: All user-provided class destructors, deallocation functions,
  move constructors, move assignment operators and swap functions shall not exit
  with an exception
- **M6-4-5**: Unconditional `break` required at end of every non-empty switch
  clause
- **A18-1-1**: C-style arrays shall not be used — use `std::array` or `std::vector`

### Test Conventions — GTest (C++)

Same GTest conventions as the C/MISRA profile plus:

- Use typed tests (`TYPED_TEST`) for template code
- Test fixtures (`TEST_F`) for any test requiring setup/teardown
- Death tests (`EXPECT_DEATH`) for assertions and precondition violations
- No `new` in test code — use stack allocation or `std::make_unique`
- Mock objects via Google Mock (`EXPECT_CALL`) — no hand-rolled mocks
- Name pattern: `TEST_F(ModuleFixture, FunctionName_Scenario_ExpectedOutcome)`

---

## Smelt Configuration File

`smelt.toml` at the repo root controls global behavior:

```toml
[smelt]
profile     = "python_default"   # profile name or path to .toml
output_dir  = "smelt_output/"
log_level   = "info"             # debug | info | warn
# docs: https://runsmelt.dev

[llm]
provider    = "anthropic"
model       = "claude-sonnet-4-5"
max_tokens  = 8192

[llm.system]
# Injected into every generation prompt. Keep this honest about the loop.
preamble    = """
You are generating code that will be scored and iteratively refined.
Do not hardcode values to pass specific tests.
Do not modify test files — they are read-only ground truth.
Fix the failures described. Do not introduce new ones.
"""
```

---

## Output Structure

Every Smelt run writes to `smelt_output/<run_id>/`:

```
smelt_output/<run_id>/
├── manifest.json           # frozen test hashes, profile, spec hash
├── frozen_tests/           # immutable after Phase 1
│   └── test_<module>.py    # (or test_<module>.cpp)
├── iterations/
│   ├── 001/
│   │   ├── code/           # generated code this iteration
│   │   ├── compliance.json # scorer output
│   │   ├── goal.json       # test runner output
│   │   └── score.json      # composite score + failure detail
│   └── ...
├── final/
│   └── code/               # code from the converged (or capped) iteration
└── trace.json              # full score history across all iterations
```

---

## Adding a New Scorer

1. Create `smelt/scorers/<name>_scorer.py`
2. Implement `BaseScorer`:

```python
from smelt.scorers.base import BaseScorer, ScoreResult

class MyScorer(BaseScorer):
    name = "my_scorer"

    def score(self, code_path: Path, config: dict) -> ScoreResult:
        # Run your tool, parse output
        # Return ScoreResult(score=float, violations=list[Violation])
        ...
```

3. Add to `smelt/scorers/__init__.py` registry
4. Reference by name in any profile's `scorers.active` list

The Crasis scorer slot follows this same interface. When Crasis specialists exist,
they register here. The loop doesn't care what's inside the scorer — only that it
returns a float and a list of violations with enough detail to reprompt on.

---

## Adding a New Test Runner

1. Create `smelt/runners/<name>_runner.py`
2. Implement `BaseRunner`:

```python
from smelt.runners.base import BaseRunner, RunResult

class MyRunner(BaseRunner):
    name = "my_runner"

    def run(self, test_path: Path, code_path: Path, config: dict) -> RunResult:
        # Execute tests, parse results
        # Return RunResult(passed=int, failed=int, failures=list[Failure])
        ...
```

---

## Non-Negotiables

These rules apply regardless of language, profile, or configuration:

1. Never write to frozen test files
2. Never generate code that detects it is being tested and changes behavior
3. Always include specific failure detail in reprompts — score alone is not a prompt
4. Always write the iteration trace — a run with no trace is an invalid run
5. Never exit CONVERGED with a mandatory MISRA or AUTOSAR violation outstanding
6. The mutation gate runs before freezing — it cannot be skipped via config
7. **The code generator never sees test source code — ever.**

### Rule 7 — Black Box Generation

The Phase 2 generation prompt contains:
- The original spec
- The original test goals (natural language)
- Test function *signatures only* — names and parameters, no assertions
- Failure detail from the previous iteration — test name, expected vs actual, traceback

The Phase 2 generation prompt never contains:
- Test source code
- Test assertions
- Any content from the frozen test file beyond function signatures

**Why this matters:** If the generator sees test source it reverse-engineers the
implementation from the assertions rather than deriving it from the spec. It will
match the test's implementation strategy, expose internal state that tests happen
to reference, and converge in one iteration by reading the answers rather than
solving the problem. This produces code that is correct-by-inspection rather than
correct-by-design.

Black box generation means the generator sees exactly what a developer sees before
a test suite exists — the requirements, not the verification mechanism. The loop
drives convergence through failure detail alone. The generator learns what failed
and what was expected, never how the test is written.

This is the architectural guarantee that makes the loop meaningful. Violating it
produces Demo 1. Honoring it produces Demo 2.
