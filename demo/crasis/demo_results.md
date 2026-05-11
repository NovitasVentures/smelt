# Demo 4 — Crasis Architectural Scoring: Results

**Run ID:** 20260511_135357  
**Status:** CONVERGED in 5 iterations  
**Final composite score:** 0.934

---

## Pipeline

```
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/
     ↓  extracted 10 architectural principles; wrote YAML specs
     ↓  human review of specs/

smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm
     ↓  trained 9 active ONNX specialists (local, no API at inference time)

smelt run --spec demo/crasis/coffeeloop_spec.md \
          --goals demo/crasis/coffeeloop_goals.md \
          --profile smelt/config/profiles/crasis_python.toml \
          --module coffeeloop
     ↓  CONVERGED in 5 iterations
```

---

## Specialists trained

| Specialist | Principle | Mandatory |
|---|---|---|
| `single-exit-path` | Functions must have exactly one return point | yes |
| `bare-except-clause` | No bare `except:` — always name the exception type | yes |
| `swallowed-exception` | Caught exceptions must not be silently discarded | yes |
| `missing-exception-rewrap` | Low-level errors must be wrapped in domain exceptions at service boundaries | yes |
| `exception-boundary-handling` | Exception handling must follow boundary patterns | no |
| `shared-core-dry` | Shared types come from `coffeeloop_core`, not defined locally | no |
| `duplicate-schema-definition` | Schemas must not be redefined locally | no |
| `duplicate-error-code-definition` | Error codes must not be redefined locally | no |
| `duplicate-response-envelope-definition` | Response envelopes must not be redefined locally | no |

One specialist (`multiple-return-statements`) was retired to `specialists/_retired/` after consolidation: it described the same principle as `single-exit-path` and produced false positives on void functions. The retrained `single-exit-path` specialist covers both with explicit void-function ignore cases.

---

## Convergence trace

| Iter | Compliance | Goal | Composite | Notes |
|---|---|---|---|---|
| 1 | 0.903 | 0.960 | 0.867 | mandatory crasis violations + 1 test failure |
| 2 | 0.923 | 1.000 | 0.923 | all tests pass; threshold met; no mandatory violations |
| 3 | 0.922 | 0.640 | 0.590 | test regression; crasis still firing |
| 4 | 0.867 | 0.960 | 0.832 | compliance dip; crasis repairs tests but introduces violations |
| **5** | **0.934** | **1.000** | **0.934** | **CONVERGED** |

Iteration 1 crasis violations (mandatory, blocked CONVERGED):
- `ARCH:single-exit-path [mandatory]` — two methods had multiple return paths
- `ARCH:exception-boundary-handling` — `InventoryManager` not re-wrapping at boundaries
- `ARCH:shared-core-dry` — file-level local type definitions

---

## Test suite

Phase 1 synthesized **25 tests** across 247 lines covering:
- `InventoryManager`: availability check (parametrized), reservation, idempotency, error cases
- `NotificationService`: dispatch for all `OrderStatus` values, empty ID guard
- `OrderGateway`: happy path, inventory failure, notification failure (non-fatal), type integrity, exception wrapping

Mutation gate: **50% kill rate** required and achieved. The SEiP accumulator pattern (`result = x; ...; return result`) generates inherently unkillable mutants on the initial assignment — equivalent mutants that don't change observable behavior. The threshold is calibrated for this.

---

## Findings from this run

### Specialist quality and the void-function corner case

The `multiple-return-statements` specialist (trained on SAD section 6.1) produced false positives on `__init__` methods at 92–96% confidence, blocking convergence. Root cause: void functions have zero return statements, which the specialist misclassified as "multiple exits."

The `single-exit-path` specialist was retrained with explicit corner cases:
```python
# Must NOT fire — zero return statements, void function
def __init__(self, inventory, notifications):
    self.inventory = inventory
    self.notifications = notifications

# Must NOT fire — single accumulator return
def check_availability(self, items):
    result = False
    ...
    result = available
    return result

# Must fire — two returns
def guard(x):
    if x is None:
        return None
    return expensive(x)
```

After retraining, `__init__` confidence dropped from ~89% to 58% (below 0.80 threshold). Real two-return violations score 80–97%.

**Implication for future specialists:** Any principle that can be zero-satisfied (void functions for exit-path rules, empty functions for any rule) needs explicit zero-case examples in `eval_on`. This is the ONNX equivalent of the void-function edge case in static analysis rules.

### Mutation gate environment isolation

mutmut spawns a subprocess pytest that does not inherit the current virtual environment's installed packages. Fix: inject `site.getsitepackages()` into both `PYTHONPATH` (subprocess env) and `conftest.py` (`sys.path`). Use `sys.executable -m mutmut` instead of bare `mutmut` to ensure the same interpreter.

mutmut 2.x SQLite status values differ from what the documentation implies:
- Killed: `ok_killed` (not `killed`)
- Survived: `bad_survived` (not `survived`)
- Suspicious: `ok_suspicious` (not `suspicious`)
- Timeout: `bad_timeout` (not `timeout`)

### Compound principle extraction

The initial extraction produced `exception-boundary-handling` as a single specialist covering three distinct failure modes (bare except, swallowed exceptions, missing re-wrap). A compound trigger — any trigger containing "or" between distinct failure patterns — almost always indicates the principle should be split. The extraction prompt now enforces Rule 6: one violation pattern per principle.

---

## Final generated code

`coffeeloop.py` — 123 lines, all three services:
- `InventoryManager`: stock management with single-exit-path accumulator pattern
- `NotificationService`: status dispatch, single exit
- `OrderGateway`: orchestration with boundary exception wrapping

All `coffeeloop_core` types used correctly. Mandatory architectural principles satisfied at convergence.

---

## Profile

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
mandatory_principles = [
  "single-exit-path",
  "bare-except-clause",
  "swallowed-exception",
  "missing-exception-rewrap",
]
```
