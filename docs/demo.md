# Smelt Demo — Rate Limiter

This document records the first end-to-end run of Smelt: a full Phase 1 → Phase 2 execution
that synthesized tests, validated them with a mutation gate, and generated a passing,
compliant implementation autonomously.

---

## What was run

```bash
smelt --spec demo/rate_limiter_spec.md --goals demo/rate_limiter_goals.md
```

**Spec:** A thread-safe token bucket rate limiter — configurable rate and burst, `acquire()`
blocks or raises `RateLimitExceeded`, thread-safe for concurrent callers.

**Goals:** 11 behaviors covering basic rate limiting, burst capacity, burst exceeded raises,
rate recovery timing, thread safety under 10 and 20 concurrent callers, and edge cases
(zero tokens, single-token burst, fractional rate, default parameter).

**Profile:** `python_default` — ruff compliance scorer, pytest runner, mutmut mutation gate.

---

## Phase 1 — Test Synthesis

Smelt sent the spec and goals to Claude (claude-sonnet-4-5) and received a 17-test pytest
suite covering all goal behaviors.

Before freezing, Smelt ran the mutation gate:

- Generated a stub implementation (all functions returning `None` / raising `NotImplementedError`)
- Ran mutmut against the stub with the generated tests
- **Kill rate: 100%** — every mutant was caught
- Gate threshold: 70% — passed on first attempt

The test file was written to `smelt_output/<run_id>/frozen_tests/test_implementation.py`
and its SHA-256 hash recorded in `manifest.json`. The hash is checked at the start of every
Phase 2 iteration — any modification aborts the run.

---

## Phase 2 — Generation Loop

Smelt sent the spec and the frozen test source to Claude and received an implementation.

**Iteration 1:**

| Score | Value |
|---|---|
| compliance (ruff) | 1.00 |
| goal (pytest) | 1.00 |
| composite | 1.00 |

Both thresholds satisfied (compliance ≥ 0.95, goal ≥ 1.00) → **CONVERGED**.

Terminal output:

```
─────────────────────────── Phase 2 — Generation Loop ───────────────────────────
╭──────────────────────── ✓ CONVERGED  iteration 1/20 ─────────────────────────╮
│   compliance   ██████████  1.00                                              │
│   goal         ██████████  1.00                                              │
│   composite    ██████████  1.00                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

✓ CONVERGED  in 1 iteration(s)  composite=1.00
```

---

## Generated Implementation

The final implementation — generated without any human edits:

```python
import threading
import time


class RateLimitExceeded(Exception):
    pass


class TokenBucket:
    def __init__(self, rate: float, burst: int):
        if rate <= 0:
            raise ValueError("Rate must be positive")
        if burst <= 0:
            raise ValueError("Burst must be positive")

        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1):
        if tokens > self.burst:
            raise RateLimitExceeded(
                f"Requested {tokens} tokens exceeds burst capacity {self.burst}"
            )

        if tokens == 0:
            return

        with self.lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update

                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate

                self.lock.release()
                time.sleep(wait_time)
                self.lock.acquire()
```

Notable properties of the generated code:
- Correct token bucket math: tokens replenish continuously, capped at `burst`
- Thread-safe via a `threading.Lock`, with lock-release-sleep-reacquire to avoid
  blocking other threads during waits
- `RateLimitExceeded` raised immediately (no sleep) when `tokens > burst`
- Zero ruff violations — passes the compliance scorer at 1.00 on first generation

---

## Output Artifacts

All run artifacts are written to `smelt_output/<run_id>/`:

```
smelt_output/20260509_034350/
├── manifest.json             # spec hash, test hash, mutation kill rate
├── frozen_tests/
│   └── test_implementation.py   # 17 tests, immutable
├── iterations/
│   └── 001/
│       ├── code/
│       │   └── implementation.py
│       ├── compliance.json   # ruff score + violations (empty)
│       ├── goal.json         # pytest pass/fail counts
│       └── score.json        # composite score
├── final/
│   └── code/
│       └── implementation.py
└── trace.json                # full score history
```

`trace.json`:
```json
{
  "run_id": "20260509_034350",
  "status": "CONVERGED",
  "iterations": [
    { "n": 1, "compliance": 1.0, "goal": 1.0, "composite": 1.0 }
  ]
}
```

---

## What this proves

1. **Tests generated from a spec are non-trivial.** The mutation gate killed 100% of
   mutants against a stub — the tests would catch any incorrect implementation.

2. **Tests are immutable.** The manifest hash is verified before every iteration.
   The LLM has no path to modify the frozen tests.

3. **Score = compliance × goal.** Both must converge. A compliant but broken
   implementation scores 0.0 on composite. A passing but non-compliant one cannot
   exit either.

4. **Failure detail drives targeted fixes.** The reprompt always includes exact ruff
   rule IDs, line numbers, and pytest failure names — not just a score.

5. **The loop exits only on correct, compliant code.** In this run it converged in
   one iteration. On harder problems or with a weaker model, the loop will reprompt
   with specific failures and iterate until both thresholds are met or the cap is hit.

---

## Known behavior on this system

Mutmut 3.x is incompatible with WSL2 (it walks `/run/udev/watch` symlinks and crashes).
Smelt pins `mutmut==2.5.1` in `pyproject.toml`. The mutation gate reads the mutmut
SQLite cache directly (`status` column: `ok_killed`, `survived`, `timeout`) rather than
parsing CLI output, which is stable across minor mutmut 2.x releases.
