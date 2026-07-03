# Demo 8 — EV Battery Management System: A Compliance Suite Written in English

## What This Demo Shows

Demo 8 demonstrates Smelt enforcing a **complete domain-specific safety compliance
suite authored in plain English** against generated C++14 — for a domain where the
failure modes are physical: an EV battery pack.

The compliance suite is an ISO/IEC/IEEE 42010 Software Architecture Document
(`demo/bms/SAD.md`). From it, Smelt derives five enforcement mechanisms across
three tiers:

| Principle (SAD §) | Tier | Enforcer | Trained? |
|---|---|---|---|
| Layer Isolation (6.1) | Systemic | LayerScorer (dependency graph) | No — deterministic |
| Fault Latching Discipline (6.2) | Local | Crasis ONNX `fault-cleared-outside-reset` | NEW |
| Raw Value Quarantine (6.3) | Local | Crasis ONNX `raw-threshold-comparison-in-decision-logic` | NEW |
| Diagnostic Query Purity (6.4) | Local | Crasis ONNX `state-mutation-in-diagnostic-query` | NEW |
| Output Parameter Purity (6.5) | Local | Crasis ONNX `output-param-written-before-error-check` | REUSED from Demo 7 |
| Fixed-Width Types (ADR-002) | Local | Crasis ONNX `platform-dependent-integer-types` | REUSED from Demo 7 |
| C++14 style baseline | Syntactic | clang-tidy (hicpp/cert/cppcoreguidelines) | No |

Core claims:

1. **If a safety rule can be written in English, Smelt can enforce it in code.**
   Three new specialists are trained from SAD sentences; no rule engine, no AST
   pattern DSL, no hand-written checker.
2. **Compliance knowledge transfers.** Two of the five specialists were trained on
   a different project (Demo 7's sensor pipeline) and are reused unchanged.
3. **This closes the last language box on the roadmap:** C++14 / AUTOSAR-aligned /
   GTest, on the infrastructure built for Demo 7.

---

## The Money Moment

The behavioral test suite (`bms_goals.md`, ~60 tests) is deliberately **structurally
blind** to the mandatory architectural principles. The demo's central frame: all
tests green, run not converged — because the architecture is wrong in ways no test
can see.

| Violation | Why every test passes anyway |
|---|---|
| `supervision/` includes `hal/` directly | No test can observe an `#include` path. Behavior is identical. |
| `update_cell` silently un-latches a fault when the reading returns in-range | No goal observes fault state in the recovery window — tests check fault-after-injection and fault-after-reset only. A self-clearing fault manager passes all of them. |
| Threshold compared in raw ADC counts (`raw > 3440`) instead of millivolts (`mv > 4200`) | Truncating integer conversion is monotonic — the two comparisons are behaviorally identical on this hardware. Only the *structure* is wrong. |
| `get_cell_fault` clears the fault it reports (read-clears) | No goal reads the same fault twice. Each test performs one query per scenario. |

The domain stakes write the post for us: a BMS that un-latches an overvoltage fault
when the cell voltage dips back in range **re-closes the contactor on a damaged
cell**. Intermittent faults — the loose sense wire, the cell oscillating around a
thermal limit — are exactly the ones that must latch, and exactly the ones a
behavioral test suite never catches.

### Why the LLM violates each principle naturally

- **Layer Isolation:** `poll_cell` needs raw data that lives two layers down. The
  monitoring indirection contains no interesting logic, and the generator collapses
  it under iteration pressure — the same shortcut a human takes at a deadline.
  (Observed live in Demo 7, iteration 1.)
- **Fault Latching:** the path-of-least-resistance implementation of "evaluate
  values against thresholds and record the corresponding fault" is a fresh
  recompute with an `else` that writes `FaultType::NONE`. The spec is deliberately
  silent about the recovery window; only the SAD says faults latch.
- **Raw Value Quarantine:** if the generator shortcuts the layers, the raw counts
  are already in hand — comparing them directly is one line shorter than
  converting first. Pairs naturally with the layer violation.
- **Query Purity:** read-clears is a pervasive idiom in embedded training data
  (hardware status registers clear on read); `get_cell_fault` is exactly the
  signature where it surfaces.

### Honest-reporting commitment (Demo 4a precedent)

Which violations the generator actually produces is an empirical question. Demo 4a
showed Crasis staying silent when the spec over-determined the implementation, and
we reported that as a negative result. Same rule here: the results writeup reports
which specialists fired, which stayed silent, and why — the layer violation and the
else-clear are the two we expect with high confidence; raw-quarantine and
read-clears may not occur naturally. A specialist that stays silent is still part
of the compliance surface (regression protection), but the post only claims what
the trace shows.

---

## The "AUTOSAR" Claim — Exact Phrasing

The claim is **"AUTOSAR C++14-aligned enforcement"** — never "AUTOSAR certified"
or "AUTOSAR compliant."

- Upstream clang-tidy ships **no** `autosar-*` checks (verified: the glob matches
  zero checks on LLVM 18). Certified AUTOSAR checking requires commercial tools
  (Polyspace, Axivion, Parasoft).
- What the profile actually enforces: AUTOSAR C++14's headline constraints encoded
  three ways — SAD ADRs backed by Crasis specialists (`platform-dependent-integer-types`
  maps directly to AUTOSAR A3-9-1; no-exceptions is ADR-001 per A15-5-3), the
  closest published clang-tidy supersets (`hicpp-*`, `cert-*`,
  `cppcoreguidelines-*`), and spec conventions (scoped enums, `nullptr`,
  `constexpr`, no dynamic allocation, no virtuals).
- Overclaiming in a public post invites correction from exactly the audience the
  post targets. The aligned-not-certified phrasing is load-bearing.

---

## The Pipeline (4 Steps)

### Step 1 — `smelt arch-import`

```bash
smelt arch-import --doc demo/bms/SAD.md --specs-dir demo/bms/specs/
```

Expected routing: four function-level principles → Crasis YAML specs; Layer
Isolation (6.1) → `demo/bms/specs/layer-isolation.layer.toml` (cross-file,
no training). The routing notice printed by arch-import makes the split explicit.

### Step 2 — Human Review Gate

- Replace extractor-drafted `eval_on` sets with the authored shape catalogs from
  `demo/bms/specialist_authoring.md` (method-inventory-first discipline).
- Align the extractor-generated YAML `name:` fields with the names in
  `demo8_bms.toml` (`fault-cleared-outside-reset`,
  `raw-threshold-comparison-in-decision-logic`,
  `state-mutation-in-diagnostic-query`) — Demo 7 lost a full commit (f47045b) to
  name drift between specs, profile, and built specialists.
- **Delete the generated YAMLs for the two reused specialists**
  (`output-param-written-before-error-check`, `platform-dependent-integer-types`) —
  their models are copied from Demo 7, not retrained. Leaving the YAMLs in place
  would make arch-build retrain them (~3000 API calls each, wasted).
- Confirm `layer-isolation.layer.toml` matches the `[scorers.layer]` block in
  `demo8_bms.toml` (layers: hal, monitoring, supervision).

### Step 3 — `smelt arch-build` + verification

```bash
cp -r demo/sensor/specialists/output-param-written-before-error-check-onnx \
      demo/sensor/specialists/platform-dependent-integer-types-onnx \
      demo/bms/specialists/

smelt arch-build \
  --specs-dir demo/bms/specs/ \
  --models-dir demo/bms/specialists/ \
  --profile smelt/config/profiles/demo8_bms.toml \
  --confirm
```

Then the full `crasis classify` verification pass from
`demo/bms/specialist_authoring.md` — every shape, every method, all five
specialists — before any `smelt run`. Never run the loop against an unverified
specialist (Demo 6, builds 1–3).

### Step 4 — `smelt run`

```bash
smelt run \
  --spec demo/bms/bms_spec.md \
  --goals demo/bms/bms_goals.md \
  --profile smelt/config/profiles/demo8_bms.toml \
  --module bms
```

After Phase 1, inspect `smelt_output/<run_id>/frozen_tests/` for any test that
asserts fault state after an in-range update (a self-clearing assertion would
hard-conflict with mandatory principle 6.2 and guarantee UNCONVERGED). The goals
enumeration is designed to prevent this; verify before Phase 2 spends budget.

---

## Build-Session Prerequisites (infrastructure)

1. **`smelt/runners/gtest_runner.py` line ~65:** `_CMAKE_TEMPLATE_CPP` hardcodes
   `set(SRC_DIRS hal processing application common)`. Demo 8's layers are
   `hal monitoring supervision` — parameterize SRC_DIRS from the profile's
   `[scorers.layer].layers` (plus `common`), or the build will silently compile
   nothing from `monitoring/` and `supervision/`.
2. **Crasis scans only `.cpp/.cc/.cxx`:** the spec's "definitions in `.cpp` only"
   convention is load-bearing — inline header definitions would be invisible to
   every specialist.
3. **LayerScorer maps by top-level directory prefix:** the spec's layer-prefixed
   include convention (`#include "hal/cell_sensor.h"`) is likewise load-bearing.
4. `demo7_sensor.toml` still lists the inert `autosar-*` clang-tidy glob — drop it
   there too before anything is screenshotted.

---

## Expected Iteration Arc (to be replaced by the real trace)

**Iteration 1:** plausible implementation; likely `supervision/` includes
`hal/cell_sensor.h` directly, and `update_cell` else-clears. All or most GTests
pass. LayerScorer fires `[mandatory]`; `fault-cleared-outside-reset` fires
`[mandatory]`. Compliance below threshold; CONVERGED blocked twice over.

**Iterations 2–3:** reprompt failure detail names the rule, file, line, and the
SAD rationale. Generator routes acquisition through `CellMonitor`, removes the
else-clear. Score climbs.

**Convergence:** compliance ≥ 0.90, all tests pass, zero mandatory violations.
Target: ≤ 6 iterations (cap 15; Demo 4b needed 13 under pure architectural
pressure).

---

## Post Hooks (LinkedIn / X)

- "Every test passed. The system still refused to ship it."
- "A BMS that quietly un-latches a fault is how a pack catches fire. No unit test
  in this suite could catch it — the architecture document did."
- "We wrote the safety rule in English. Twenty minutes later it was a 4 MB ONNX
  model rejecting non-compliant C++."
- "Two of the five compliance specialists were trained on a different project and
  reused unchanged."
- The trace table (iteration × compliance × goal × violations) is the visual: tests
  green from iteration 1, compliance climbing until the mandatory violations clear.
