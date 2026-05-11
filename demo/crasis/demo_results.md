# Demo 4 — Crasis Architectural Scoring: Results

**Run ID:** 20260511_215718  
**Status:** CONVERGED in 2 iterations  
**Final composite score:** 0.995

---

## Pipeline

```
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/
     ↓  extracted 10 architectural principles; wrote YAML specs
     ↓  human review of specs/

smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm
     ↓  trained 5 active ONNX specialists (local, no API at inference time)

smelt run --spec demo/crasis/coffeeloop_spec.md \
          --goals demo/crasis/coffeeloop_goals.md \
          --profile smelt/config/profiles/crasis_python.toml \
          --module coffeeloop
     ↓  CONVERGED in 2 iterations
```

---

## Active specialists

| Specialist | Principle | Chunk level | Mandatory |
|---|---|---|---|
| `single-exit-path` | Functions must have exactly one return point | function | yes |
| `bare-except-clause` | No bare `except:` — always name the exception type | function | yes |
| `swallowed-exception` | Caught exceptions must not be silently discarded | function | yes |
| `missing-exception-rewrap` | Low-level errors must be wrapped in domain exceptions at service boundaries | function | yes |
| `exception-boundary-handling` | Exception handling must follow boundary patterns | function | no |

### Retired specialists

These were trained but retired to `specialists/_retired/` after integration:

| Specialist | Reason |
|---|---|
| `multiple-return-statements` | Duplicate of `single-exit-path`; false positives on `__init__` methods |
| `shared-core-dry` | File-level chunking caused false positives on service class definitions |
| `duplicate-schema-definition` | Same false positive pattern as `shared-core-dry` |
| `duplicate-error-code-definition` | Same false positive pattern |
| `duplicate-response-envelope-definition` | Same false positive pattern |

---

## Convergence trace (final run)

| Iter | Compliance | Goal | Composite | Notes |
|---|---|---|---|---|
| 1 | 0.993 | 0.538 | 0.535 | 12/26 test failures (OrderStatus attribute error); crasis clean |
| **2** | **0.995** | **1.000** | **0.995** | **CONVERGED** — all tests pass, no ARCH violations |

---

## Why Crasis didn't fire

The convergence trace above is honest but incomplete. Crasis scored **1.0 on iteration 1** — all five active specialists passed. The only friction in this run was behavioral: the LLM hallucinated `OrderStatus.COMPLETED`, an enum value that doesn't exist in `coffeeloop_core`. Fixing that enum reference (and resolving four mypy annotation errors) was sufficient to reach CONVERGED. Crasis was a silent observer.

**Why the spec made architectural compliance easy**

The CoffeeLoop spec explicitly describes error propagation: `InventoryError` must surface as `OrderError`, notification failures must be logged not raised, unexpected exceptions must surface as `OrderError`. Any LLM that reads that spec and writes code to satisfy it ends up with:

- A single return point at the end of `process_order` (exception raises don't count as returns)
- Named exception types in every `except` clause (the spec tells you which exceptions to catch)
- Exceptions re-wrapped at the service boundary (the spec mandates it)

The architectural principles enforced by the five specialists are what the spec requires anyway. There is no tension. Satisfying the behavioral spec and satisfying the architecture are the same task, so the LLM satisfied both simultaneously without any architectural feedback.

**What a meaningful Crasis test requires**

For Crasis to do real work, the demo needs a task where the naive, behaviorally-correct first implementation is architecturally wrong. Specifically:

1. A behavioral spec that is silent on implementation structure — it describes *what* the code must do, not *how* it must be organized
2. An architectural principle that the LLM will violate naturally, because the antipattern is the path of least resistance
3. Test goals that verify output correctness only — nothing that hints at control-flow or structural choices

The CoffeeLoop spec fails condition 1: it describes exception propagation in enough detail that the LLM's natural implementation is already compliant. A well-written behavioral spec that happens to describe the same structural patterns the SAD mandates will always produce coincidental compliance.

Demo 4b addresses this directly. See `demo/crasis/reportservice_spec.md`.

---

## Score formula

```
crasis_score = 1.0 - (weight of violated principles) / (total principle weight)
```

A principle is **violated** if ANY chunk anywhere in the codebase triggers it at or above the confidence threshold. One hit counts as a full principle violation, weighted by the principle's importance. All active specialists have weight 1.0 (mandatory/shall principles from the SAD).

With 5 specialists at weight 1.0:
- 0 violated → 1.000
- 1 violated → 0.800 (below 0.90 compliance threshold)
- 2 violated → 0.600

The composite score is `compliance × goal`, both normalized 0–1. Neither compensates for the other.

---

## Engineering findings

### 1. Principle-based vs chunk-based scoring

The score penalizes violated **principles**, not violated **chunks**. Three different implementations of the chunk-based formula were tried and rejected:

- `1.0 - violations / (chunks × specialists)` — too lenient; 8 violations in 1000 chunks scores 0.999
- `1.0 - sum(max_weight per violated chunk) / total_chunks` — better but doesn't answer "how many architectural rules did the code break"
- **`1.0 - violated_weight / total_weight`** — correct; one principle broken anywhere = full penalty for that principle

### 2. File-level specialists produce false positives

The DRY principles (`shared-core-dry`, `duplicate-*`) use `chunk_level: file` — the entire file is fed to the specialist. File-level specialists cannot distinguish "new service class" from "duplicate data class" when both appear in the same file. They fired at 80–95% confidence on code that correctly imported from `coffeeloop_core` but also defined `InventoryManager` and `OrderGateway`.

**Implication:** File-level specialists require training data that explicitly includes correct multi-class modules. A spec whose trigger is "defines a type locally that should come from an external package" must have eval_on examples that include correct single-file multi-class modules as negative cases.

### 3. `multiple-return-statements` == `single-exit-path`

The SAD section 6.1 produced two specialists with identical descriptions and triggers. The `multiple-return-statements` specialist had worse false positive behavior on `__init__` methods (92–96% confidence on zero-return methods). The lesson: **identical principles should not be split** — the extraction prompt now enforces "one violation pattern per principle" and checks for semantic duplicates.

### 4. Void function corner case

Any principle involving return-statement counting must include `__init__` and other void functions as explicit negative examples in `eval_on`. A function with zero return statements satisfies a "single exit path" rule — but the original specialist scored it at 89–94% positive. After retraining with void-function corner cases, the same code scores 55–58% (below the 0.80 confidence threshold).

### 5. mutmut environment isolation

mutmut spawns a subprocess pytest that cannot import packages from the parent virtual environment unless explicitly provided. Fix:
- Inject `site.getsitepackages()` into `PYTHONPATH` (subprocess env) and `conftest.py` (`sys.path`)  
- Use `sys.executable -m mutmut` instead of bare `mutmut` to pin the interpreter

mutmut 2.x SQLite status names differ from documentation: `ok_killed`, `bad_survived`, `ok_suspicious`, `bad_timeout` (not `killed`, `survived`, `suspicious`, `timeout`).

### 6. Baseline tests must pass for mutmut to produce mutants

When the Phase 1 baseline fails more than 50% of tests, mutmut's initial dry run fails and it reports 0 mutants — making the kill rate always 0%. The baseline generation prompt now explicitly states which external packages are installed and that their types must be used directly (not redefined). A pre-check validates the baseline passes before invoking mutmut.

---

## Profile

```toml
[thresholds]
compliance = 0.90
goal       = 1.00
mutation   = 0.50  # SEiP pattern generates equivalent mutants on result-accumulator initialization

[scorers]
active  = ["ruff", "mypy", "crasis"]
weights = { ruff = 0.15, mypy = 0.15, crasis = 0.70 }

[scorers.crasis]
models_dir           = "specialists"
confidence_threshold = 0.80
mandatory_principles = [
  "single-exit-path",
  "bare-except-clause",
  "swallowed-exception",
  "missing-exception-rewrap",
]
```

---

# Demo 4b — Result Accumulator Pattern: Results

**Run ID:** 20260511_233113  
**Status:** CONVERGED in 13 iterations  
**Final composite score:** 0.99

---

## Pipeline

```
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/
     ↓  extracted 6 principles (SAD extended with section 6.4 — RAP)
     ↓  human review of specs/result-accumulator-pattern.yaml

smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm
     ↓  trained 14 specialists total; result-accumulator-pattern-onnx/ added

smelt run --spec demo/crasis/reportservice_spec.md \
          --goals demo/crasis/reportservice_goals.md \
          --profile smelt/config/profiles/crasis_python.toml \
          --module reportservice
     ↓  CONVERGED in 13 iterations
```

---

## Active specialists (Demo 4b)

| Specialist | Principle | Chunk level | Mandatory |
|---|---|---|---|
| `single-exit-path` | Functions must have exactly one return point | function | yes |
| `bare-except-clause` | No bare `except:` — always name the exception type | function | yes |
| `swallowed-exception` | Caught exceptions must not be silently discarded | function | yes |
| `missing-exception-rewrap` | Low-level errors must be wrapped in domain exceptions at service boundaries | function | yes |
| `result-accumulator-pattern` | Functions must declare a result variable at top and return it exactly once at the bottom | function | yes |

`exception-boundary-handling` was included initially but removed after it produced consistent false positives at 92–98% confidence on every method in `ReportService` regardless of implementation. See engineering finding 7.

---

## Convergence trace (Demo 4b)

| Iter | Compliance | Goal | Composite | Crasis score | Notes |
|---|---|---|---|---|---|
| 1 | — | 0.00 | 0.00 | — | Syntax error in generated file (markdown fence leaked) |
| 2 | 0.71 | 1.00 | 0.71 | 0.60 | 31/31 tests pass; `result-accumulator-pattern` + `single-exit-path` fire on `validate` |
| 3 | 0.85 | 1.00 | 0.85 | 0.80 | `single-exit-path` fires on `summarize` |
| 4 | 0.71 | 1.00 | 0.71 | 0.60 | RAP + SEiP both fire on `validate` again |
| 5 | 0.85 | 1.00 | 0.85 | 0.80 | `single-exit-path` only |
| 6–12 | 0.71–0.85 | 1.00 | 0.71–0.85 | 0.60–0.80 | LLM oscillates between forms; RAP and SEiP alternate |
| **13** | **0.99** | **1.00** | **0.99** | **1.00** | **CONVERGED** — all specialists clean |

The behavioral correctness (31/31 tests) was stable from iteration 2 onward. All 11 subsequent iterations were driven entirely by architectural pressure from Crasis.

---

## What the converged code looks like

```python
def validate(self, order_id: str, items: list[OrderItem]) -> bool:
    is_valid = True

    if not order_id:
        is_valid = False
    elif not items:
        is_valid = False
    else:
        for item in items:
            if item.quantity <= 0:
                is_valid = False
                break
            if not item.ingredient:
                is_valid = False
                break

    return is_valid
```

The LLM's natural first-pass form was early returns from each guard clause. The converged form uses an `is_valid` accumulator with a single `return is_valid` — structurally different in a way that would not have appeared without Crasis pressure. The behavioral output is identical; only the architectural structure changed.

---

## Engineering findings (Demo 4b)

### 7. `active_specialists` allow-list is required when models_dir accumulates specialists across runs

`arch-build` rebuilds every spec in `--specs-dir`, including retired ones. Without an allow-list, the scorer loads and runs all models in `models_dir`. On the first run without filtering, 9–11 violations fired per iteration from specialists that had previously been retired for false positives — the loop could not converge because it was receiving irreconcilable feedback.

**Fix:** `active_specialists` key in the profile's `[scorers.crasis]` section. The scorer filters `toolkit.specialists()` against this list; the scoring denominator uses only active specialists. Inactive specialists remain in `models_dir` and can be re-enabled without retraining.

```toml
[scorers.crasis]
active_specialists = [
  "single-exit-path",
  "bare-except-clause",
  "swallowed-exception",
  "missing-exception-rewrap",
  "result-accumulator-pattern",
]
```

### 8. `exception-boundary-handling` is not reliably trainable on this data

`exception-boundary-handling` fired at 92–98% confidence on every method in `ReportService` across all 15 iterations of the first run, regardless of what the code did. The specialist appears to conflate "function that handles exceptions" with "function that violates exception boundary patterns" — the trigger is too broad for the training data it received. It is built, present in `specialists/`, and excluded by `active_specialists`. It requires retraining with a tighter trigger definition and explicit negative examples of correct boundary-aware exception handling before it can be safely re-enabled.

### 9. `single-exit-path` fires on RAP-compliant code intermittently

After the LLM adopted the accumulator pattern, `single-exit-path` continued to fire at 80–98% confidence on the same functions, alternating with iterations where it did not. This is a false positive — the code has a single `return` statement. The specialist appears sensitive to the shape of the surrounding `if/elif` chain rather than the presence of multiple `return` statements.

In Demo 4b this was not harmful: both `single-exit-path` and `result-accumulator-pattern` are pushing toward the same structural target, so their combined pressure drove convergence even when `single-exit-path` was misidentifying the violation. In a scenario where the principles are independent, intermittent false positives from one mandatory specialist would prevent convergence entirely. The fix is the same as finding 4: add RAP-compliant accumulator functions as explicit negative examples in `eval_on` during retraining.

### 10. Spec–architecture tension is the necessary condition for Crasis to matter

The decisive difference between Demo 4a (2 iterations, Crasis silent) and Demo 4b (13 iterations, Crasis driving) is the relationship between the behavioral spec and the architectural principles:

- **Demo 4a:** The spec described exception propagation explicitly enough that following it naturally produced architecturally compliant code. Crasis had nothing to say.
- **Demo 4b:** The spec described only input/output behavior. The architectural principle (RAP) constrains *how* functions are structured, which is orthogonal to what they return. The LLM's natural style (early returns) satisfies the spec and violates the architecture simultaneously.

The lesson: **architectural enforcement is only observable when the architecture constrains something the behavioral spec does not.** A spec that leaks structural requirements will always produce coincidental compliance. Crasis is most valuable when the spec is silent on implementation form.

---

## Profile (Demo 4b)

```toml
[thresholds]
compliance = 0.90
goal       = 1.00
mutation   = 0.50

[scorers]
active  = ["ruff", "mypy", "crasis"]
weights = { ruff = 0.15, mypy = 0.15, crasis = 0.70 }

[scorers.crasis]
models_dir           = "specialists"
confidence_threshold = 0.80
active_specialists   = [
  "single-exit-path",
  "bare-except-clause",
  "swallowed-exception",
  "missing-exception-rewrap",
  "result-accumulator-pattern",
]
mandatory_principles = [
  "single-exit-path",
  "bare-except-clause",
  "swallowed-exception",
  "missing-exception-rewrap",
  "result-accumulator-pattern",
]
```
