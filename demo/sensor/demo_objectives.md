# Demo 7 — Systemic Drift Detection

## What This Demo Shows

Demo 7 demonstrates Smelt detecting **systemic architectural drift** — violations that
are invisible to every existing tool (linters, type checkers, ONNX classifiers) because
no single file contains the full evidence. The violation only appears when you examine
the dependency graph across multiple files and compare it against the declared architecture.

The core claim: **Smelt can enforce structural intent that exists nowhere except the SAD.**

This extends the capability demonstrated in Demos 4–6 (local-intent enforcement via Crasis)
to a fundamentally different failure class. Previous demos asked "is this function
implemented per our standards?" Demo 7 asks "has the system drifted from its intended
structure?" These are different questions requiring different scorers.

---

## What Makes This Hard

The `LayerScorer` fires on a violation that:

- Passes ruff, mypy, clang-tidy without a single warning
- Passes all GTests — the behavioral output is correct
- Would pass the Crasis ONNX specialists from Demos 4–6 — no local principle is violated
- Only becomes visible when you trace `#include` paths across the three-layer boundary

This is the exact failure mode that accumulates silently in real embedded codebases:
each engineer's change looks correct in isolation, but the aggregate erodes the layer
boundary that makes the system portable and testable.

---

## The Scenario

A three-layer embedded sensor pipeline:

```
hal/          ← SensorDriver: raw register reads
processing/   ← SensorProcessor: calibration, filtering
application/  ← SensorDispatcher: decision logic, threshold dispatch
```

The SAD declares two mandatory principles:

1. **Layer Isolation** (systemic): `application/` must never include `hal/` headers.
   All sensor data flows through `processing/`. Enforced by `LayerScorer`.

2. **Output Parameter Purity** (local): functions that communicate results via output
   parameters must not write those parameters on error return paths. Enforced by three
   Crasis ONNX specialists (`output-param-written-before-error-check`,
   `output-param-written-on-error-path`, `platform-dependent-integer-types`).

**Why the LLM violates Layer Isolation naturally:** `SensorDispatcher::sample_and_dispatch`
needs a calibrated, filtered sensor value to compare against a threshold. The direct path
is `hal::SensorDriver` called from `application/`. The processing layer intermediary adds
an indirection with no behavioral logic, which the LLM collapses under iteration pressure
("tests are failing, tighten up the implementation"). This mirrors exactly the shortcut
human engineers take under deadline pressure.

**Why tests are blind to it:** The GTest suite verifies that `sample_and_dispatch` returns
the correct `ErrorCode`, that thresholds fire at the right values, and that output
parameters are not written on error paths. It does not check which layer an include came
from. The behavioral tests pass regardless of whether `application/` includes `hal/`
directly.

---

## The Pipeline (4 Steps)

### Step 1 — `smelt arch-import`

```bash
smelt arch-import --doc demo/sensor/SAD.md --specs-dir demo/sensor/specs/
```

Reads `SAD.md`, calls Claude to extract enforceable principles, and routes them by
chunk_level:

- **Layer Isolation** → `chunk_level = "cross-file"` → routed to LayerScorer.
  Written as `demo/sensor/specs/layer-isolation.layer.toml` config snippet.
  **No ONNX training required.**

- **Output Parameter Purity** → `chunk_level = "function"` → routed to Crasis.
  Written as `demo/sensor/specs/output-param-written-before-error-check.yaml`,
  `output-param-written-on-error-path.yaml`, and `platform-dependent-integer-types.yaml`.

The routing notice printed by `arch-import` makes the enforcement split explicit:

```
Routing notice: 1 principle requires cross-file dependency analysis.
  → demo/sensor/specs/layer-isolation.layer.toml  (merge into [scorers.layer])
```

### Step 2 — Human Review Gate

The human reviews:
- `demo/sensor/specs/output-param-written-before-error-check.yaml` — Crasis spec, validate trigger/ignore/eval_on
- `demo/sensor/specs/output-param-written-on-error-path.yaml` — Crasis spec, validate trigger/ignore/eval_on
- `demo/sensor/specs/platform-dependent-integer-types.yaml` — Crasis spec, validate trigger/ignore/eval_on
- `demo/sensor/specs/layer-isolation.layer.toml` — confirm layer names and allowed edges match the project structure

The `.layer.toml` snippet for this demo has already been merged into `demo7_sensor.toml`.

### Step 3 — `smelt arch-build`

```bash
smelt arch-build \
  --specs-dir demo/sensor/specs/ \
  --models-dir demo/sensor/specialists/ \
  --profile smelt/config/profiles/demo7_sensor.toml \
  --confirm
```

Trains three Crasis specialists (the layer-isolation principle does not require
training — it runs as a deterministic graph analysis).

Before running `smelt run`, verify each specialist against the method inventory:

```bash
# Verify every method shape in specialist_authoring.md
crasis classify --model demo/sensor/specialists/output-param-written-before-error-check-onnx/ \
  --text "$(cat <method_snippet>)"
crasis classify --model demo/sensor/specialists/output-param-written-on-error-path-onnx/ \
  --text "$(cat <method_snippet>)"
crasis classify --model demo/sensor/specialists/platform-dependent-integer-types-onnx/ \
  --text "$(cat <method_snippet>)"
```

### Step 4 — `smelt run`

```bash
smelt run \
  --spec demo/sensor/sensor_spec.md \
  --goals demo/sensor/sensor_goals.md \
  --profile smelt/config/profiles/demo7_sensor.toml \
  --module sensor_pipeline
```

**Iteration 1:** The LLM generates a plausible implementation. `SensorDispatcher`
includes `hal/sensor_driver.h` directly (the natural shortcut). Several output
parameters are written at the top of their functions before error checks. Both scorers
fire:

```
[LAYER] application/sensor_dispatcher.cpp:3: violates 'layer-isolation' [mandatory]
  application/sensor_dispatcher.cpp includes 'hal/sensor_driver.h' —
  forbidden dependency: 'application' must not depend on 'hal' directly

[ARCH] application/sensor_dispatcher.cpp:24: violates 'output-param-written-before-error-check' [mandatory]
  (87% confidence) — SensorDispatcher::get_last_reading

[ARCH] processing/sensor_processor.cpp:18: violates 'output-param-written-on-error-path' [mandatory]
  (91% confidence) — SensorProcessor::acquire
```

Compliance score drops below 0.90. Both `[mandatory]` violations block `CONVERGED`.

**Iterations 2–3:** The LLM removes the direct HAL include from `application/`, routes
all sensor access through `SensorProcessor`. Fixes output parameter writes on error paths.
LayerScorer clears. Crasis specialist clears.

**Convergence:** `compliance_score >= 0.90`, all GTests pass, no `[mandatory]` violations.

---

## Setup Before Running

```bash
# Set the OpenRouter API key (required for crasis build in Step 3)
export OPENROUTER_API_KEY=sk-or-v1-...

# Run arch-import (Step 1)
smelt arch-import --doc demo/sensor/SAD.md --specs-dir demo/sensor/specs/

# Review specs, then build (Step 3)
smelt arch-build \
  --specs-dir demo/sensor/specs/ \
  --models-dir demo/sensor/specialists/ \
  --profile smelt/config/profiles/demo7_sensor.toml \
  --confirm

# Run the generation loop (Step 4)
smelt run \
  --spec demo/sensor/sensor_spec.md \
  --goals demo/sensor/sensor_goals.md \
  --profile smelt/config/profiles/demo7_sensor.toml \
  --module sensor_pipeline
```

---

## Why This Matters

Demos 4–6 proved that Smelt can enforce architectural principles that live only in
English-language documents. But those principles were all *local* — detectable by
inspecting a single function or file. The ONNX path handles that tier well.

Demo 7 proves a harder claim: **Smelt can enforce structural intent that is invisible
to any per-chunk analysis.** Layer isolation is not a property of any function. It is
a property of the dependency graph, and it can only be evaluated by comparing the
realized graph against the declared graph in the SAD.

This is the failure class that silently destroys embedded codebases over time:
- Each PR looks clean locally
- Tests pass
- Linters pass
- But the architecture slowly collapses as engineers take shortcuts that "just work"

The `LayerScorer` makes that collapse visible on iteration 1 of the generation loop.
The reprompt drives the generator to fix the structure, not just the behavior.

Two enforcement mechanisms, one coherent loop. Local principles go to Crasis.
Systemic principles go to the graph analyzer. The routing decision happens at
`arch-import` time, based on `chunk_level` in the extracted principle.

---

## Two-Tier Enforcement in One Run

| Principle | Tier | Enforcer | Weight |
|---|---|---|---|
| Layer Isolation | Systemic | LayerScorer (deterministic, no training) | 0.40 |
| Output Parameter Purity | Local | Crasis ONNX specialist | 0.40 |
| C++ Style / AUTOSAR | Syntactic | clang-tidy | 0.20 |

The compliance score is the weighted mean of all three. Both mandatory violations
must clear before `CONVERGED` is possible. The demo shows all three enforcer types
working in the same loop against the same generated code.
