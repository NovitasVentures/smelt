# Demo 4 — Crasis Architectural Scoring

## What This Demo Shows

Demo 4 demonstrates Smelt enforcing **architectural intent** extracted directly from a
Software Architecture Document (SAD). Unlike Demos 1–3, which enforce syntactic rules
(ruff, mypy) or language standards (MISRA), this demo enforces semantic design principles
using trained ONNX classifiers — no regex, no rule engines, no hand-written checks.

The core claim: **if you can write it in English, Smelt can enforce it in code.**

---

## The Pipeline (4 Steps)

### Step 1 — `smelt arch-import`

```bash
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/
```

Reads `SAD.md` (the CoffeeLoop architecture document), calls Claude to extract
enforceable architectural principles, and writes one Crasis YAML spec per principle.

Extracted principles from the CoffeeLoop SAD:
1. **single-exit-path** — every function has exactly one return statement (mandatory)
2. **shared-core-dry** — shared types imported from `coffeeloop_core`, never defined locally
3. **structured-exception-handling** — exceptions re-wrapped at service boundaries (mandatory)

The command prints a review table and exits. **No training happens here.**

### Step 2 — Human Review Gate

The human reviews the generated specs in `specs/`. Each spec contains:
- `task.trigger`: what a violation looks like (the positive class for the classifier)
- `task.ignore`: acceptable patterns that look like violations
- `quality.eval_on`: edge cases the specialist must handle correctly

This is the point where architectural intent is validated before budget is spent.
Bad specs waste training compute. The `--confirm` gate enforces the review.

### Step 3 — `smelt arch-build`

```bash
smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm
```

Calls `crasis build` for each spec. Crasis:
1. Generates synthetic training data via OpenRouter (distillable models only)
2. Distills a local BERT specialist to detect the principle's violation pattern
3. Exports to ONNX (<20MB, <10ms inference, CPU-only)

Three specialists are trained:
- `specialists/single-exit-path-onnx/` — fires when a function has multiple returns
- `specialists/shared-core-dry-onnx/` — fires when shared types are defined locally
- `specialists/structured-exception-handling-onnx/` — fires when exceptions are swallowed

### Step 4 — `smelt run`

```bash
smelt run \
  --spec demo/crasis/coffeeloop_spec.md \
  --goals demo/crasis/coffeeloop_goals.md \
  --profile smelt/config/profiles/crasis_python.toml \
  --module coffeeloop
```

The generation loop runs with `CrasisScorer` active (weight 0.6, dominant scorer).

**Iteration 1:** The LLM generates a plausible but architecturally non-compliant
implementation — multiple return statements, inline type definitions, swallowed
exceptions. CrasisScorer fires on all three specialists. The reprompt includes
specific violation locations:

```
[ARCH] coffeeloop.py:12: violates 'single-exit-path' [mandatory] (91% confidence) — OrderGateway.process_order
[ARCH] coffeeloop.py:1: violates 'shared-core-dry' (88% confidence) — coffeeloop.py
[ARCH] coffeeloop.py:47: violates 'structured-exception-handling' [mandatory] (93% confidence) — OrderGateway.process_order
```

**Iterations 2–3:** The LLM refactors to satisfy the violations. The mandatory
principle violations block `CONVERGED` exit until fully resolved — the same mechanism
MISRA mandatory violations use (Demo 3).

**Convergence:** `compliance_score >= 0.90`, all tests pass, no `[mandatory]` violations.

---

## Setup Before Running

```bash
# Install the coffeeloop_core stub package (shared types used by generated code)
pip install -e demo/crasis/coffeeloop_pkg/

# Set the OpenRouter API key (required for crasis build in Step 3)
export OPENROUTER_API_KEY=sk-or-v1-...

# Run arch-import (Step 1)
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/

# Review specs in specs/, then run arch-build (Step 3)
smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm

# Run the generation loop (Step 4)
smelt run \
  --spec demo/crasis/coffeeloop_spec.md \
  --goals demo/crasis/coffeeloop_goals.md \
  --profile smelt/config/profiles/crasis_python.toml \
  --module coffeeloop
```

---

## Why This Matters

Previous demos show Smelt enforcing objective rules: does this code pass ruff? does it
violate MISRA Rule 15.5? These rules have formal definitions. Anyone can read them.

Architectural principles are different. "All functions must have a single exit path" is
not in any language standard. "Shared types must come from the core library" is a design
decision made by a specific team for a specific system. These principles live in documents,
wikis, and ADRs — not in linters.

Crasis turns those English-language principles into local ONNX classifiers. Smelt uses
those classifiers as first-class scorers. The loop enforces the architectural intent with
the same rigor it applies to MISRA — specific violations, specific locations, reprompts
that drive convergence.

The workflow from SAD to trained specialists takes less than 30 minutes. The specialists
run at <10ms per chunk, offline, forever.

---

## Demo 4b — Proving Crasis Does Real Work

The CoffeeLoop run (Demo 4a) proved the pipeline end-to-end but exposed a structural
weakness: **the spec inadvertently made architectural compliance easy**. The exception
propagation requirements in `coffeeloop_spec.md` are descriptive enough that any LLM
following them ends up satisfying the architectural principles as a side effect. Crasis
never fired.

Demo 4b corrects this. The SAD has been extended with **section 6.4 — Result Accumulator
Pattern (RAP)**: all value-returning functions must declare a `result` variable at the
top and return it exactly once at the bottom. No early returns from conditional branches.

This principle reliably fires on LLM-generated code because early returns are the LLM's
natural style — guard clauses, short-circuit returns, and per-branch returns are
idiomatic Python and are what LLMs produce by default. A behavioral spec that says
"return True if valid, False otherwise" gives no hint that the implementation must use
a single accumulator. The LLM writes the natural form; Crasis catches it.

**New component:** `ReportService` — order summary formatting and validation.
All three methods (`summarize`, `validate`, `compute_totals`) have multiple validation
paths that will be written with early returns on a naive first pass.

**New files:**
- `demo/crasis/reportservice_spec.md` — behavioral spec (no architectural hints)
- `demo/crasis/reportservice_goals.md` — test goals (output correctness only)

**Updated SAD:** `demo/crasis/SAD.md` section 6.4 — feeds into `smelt arch-import`
to generate the RAP specialist spec.

**Run Demo 4b:**

```bash
# Re-import SAD to pick up section 6.4
smelt arch-import --doc demo/crasis/SAD.md --specs-dir specs/

# Review the new result-accumulator-pattern spec, then build
smelt arch-build --specs-dir specs/ --models-dir specialists/ --confirm

# Run the generation loop against ReportService
smelt run --spec demo/crasis/reportservice_spec.md \
          --goals demo/crasis/reportservice_goals.md \
          --profile smelt/config/profiles/crasis_python.toml \
          --module reportservice
```

Expected behavior:
- **Iteration 1:** Crasis fires on `validate` and `compute_totals` (early returns in
  conditionals). Compliance score drops below 0.90. CONVERGED blocked.
- **Iterations 2–3:** LLM refactors to accumulator pattern. Crasis violations clear.
  All tests pass. CONVERGED.
