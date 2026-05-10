# Smelt Demo 3 — C / MISRA C:2012 / GTest

Demos 1 and 2 used Python. Demo 3 switches the entire stack: C99 source,
MISRA C:2012 compliance scoring via cppcheck, and a GTest harness built with
cmake. The loop architecture is identical — spec in, compliant passing code out.

---

## What Changed

Demo 3 exercises the full C/MISRA path for the first time:

- **Language:** C99
- **Compliance scorer:** cppcheck `--addon=misra` with full MISRA C:2012 rule
  texts. Scoring: `max(0, 1 - violations / 5)` — any 5 or more non-advisory
  violations scores 0.0. Weighted 0.7 in composite compliance.
- **Secondary scorer:** clang-tidy (`cert-*`, `bugprone-*` checks). Weighted 0.3.
- **Test runner:** GTest. cmake fetches googletest via FetchContent, builds the
  test binary, runs it, parses the XML output.
- **Mutation gate:** bypassed (mutate++ not installed). MISRA and GTest scorers
  enforce correctness independently.
- **Thresholds:** compliance ≥ 0.90, goal = 1.00, max 15 iterations.

```bash
smelt \
  --spec demo/ring_buffer_spec.md \
  --goals demo/ring_buffer_goals.md \
  --profile smelt/config/profiles/c_misra.toml \
  --module ring_buffer
```

---

## Target: Fixed-Size Ring Buffer

A fixed-size circular buffer in C99 targeting embedded systems. Chosen because:

- Any naive first-pass implementation will reach for bare integer constants in
  modulo arithmetic — a direct Rule 10.4 violation (essential type mismatch)
- The data structure is naturally MISRA-compliant once type discipline is applied:
  no dynamic memory, no recursion, single exit points, fixed-width types
- Tests are exact and deterministic — FIFO ordering, boundary conditions, wrap-around

**API:** `rb_init`, `rb_push`, `rb_pop`, `rb_peek`, `rb_count`, `rb_is_full`,
`rb_is_empty`. Status codes via `RbStatus` enum (`RB_OK`, `RB_ERROR_FULL`,
`RB_ERROR_EMPTY`).

---

## Run: 20260510_011539

### Convergence Table

| Iter | misra | clang_tidy | weighted | goal  | composite | Status |
|------|-------|------------|----------|-------|-----------|--------|
| 1    | 0.000 | 1.000      | 0.300    | 1.000 | 0.300     | MISRA violations |
| 2    | 1.000 | 1.000      | 1.000    | 1.000 | 1.000     | **CONVERGED** |

### Iteration 1

**Generated:** A structurally correct ring buffer. All 33 GTest tests pass.
But 5 MISRA Rule 10.4 violations — essential type mismatch in arithmetic:

```
misra  MISRA-C2012-10.4 [required]  line 11
  Both operands of an operator in which the usual arithmetic conversions
  are performed shall have the same essential type category.

misra  MISRA-C2012-10.4 [required]  line 21
misra  MISRA-C2012-10.4 [required]  line 28
misra  MISRA-C2012-10.4 [required]  line 47
misra  MISRA-C2012-10.4 [required]  line 85
```

The root cause: modulo arithmetic against the bare integer constant `RB_CAPACITY`.

```c
rb->tail = (uint8_t)((rb->tail + 1U) % RB_CAPACITY);   /* violation */
```

`rb->tail` is `uint8_t`. `RB_CAPACITY` is an untyped `#define 16` — its
essential type is signed int. Mixing unsigned and signed in arithmetic is a
Rule 10.4 violation.

**MISRA score: 0.000** — 5 violations hits the floor (`max(0, 1 - 5/5) = 0`).
Weighted compliance: 0.30. Composite: 0.30. Loop continues.

**Reprompt includes:**
```
SCORE: 0.30  compliance=0.30  goal=1.00

COMPLIANCE FAILURES:
  misra  MISRA-C2012-10.4 [required]  line 11
    Both operands of an operator in which the usual arithmetic conversions
    are performed shall have the same essential type category.
  misra  MISRA-C2012-10.4 [required]  line 21  ...
  misra  MISRA-C2012-10.4 [required]  line 28  ...
  misra  MISRA-C2012-10.4 [required]  line 47  ...
  misra  MISRA-C2012-10.4 [required]  line 85  ...

TEST FAILURES (0):
  (none)

Fix the implementation. Return ONLY the corrected file.
```

### Iteration 2 — CONVERGED

**Generated:** All modulo operations cast to `(uint8_t)RB_CAPACITY` to match
the essential type of the left-hand operand:

```c
rb->tail = (uint8_t)((rb->tail + 1U) % (uint8_t)RB_CAPACITY);   /* fixed */
```

Zero MISRA violations. Zero clang-tidy violations. 33/33 tests pass.

- misra: 1.000
- clang_tidy: 1.000
- weighted compliance: 1.000
- goal: 1.000
- **composite: 1.000**

---

## Final Implementation

### `ring_buffer.h`

```c
#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdint.h>
#include <stdbool.h>

#ifndef RB_CAPACITY
#define RB_CAPACITY 16
#endif

typedef struct {
    uint8_t data[RB_CAPACITY];
    uint8_t head;
    uint8_t tail;
    uint8_t count;
} RingBuffer;

typedef enum {
    RB_OK          = 0,
    RB_ERROR_FULL  = 1,
    RB_ERROR_EMPTY = 2
} RbStatus;

void rb_init(RingBuffer *rb);
RbStatus rb_push(RingBuffer *rb, uint8_t value);
RbStatus rb_pop(RingBuffer *rb, uint8_t *out);
RbStatus rb_peek(const RingBuffer *rb, uint8_t *out);
uint8_t rb_count(const RingBuffer *rb);
bool rb_is_full(const RingBuffer *rb);
bool rb_is_empty(const RingBuffer *rb);

#endif
```

### `ring_buffer.c`

```c
#include "ring_buffer.h"

void rb_init(RingBuffer *rb)
{
    rb->head = 0U;
    rb->tail = 0U;
    rb->count = 0U;
}

RbStatus rb_push(RingBuffer *rb, uint8_t value)
{
    RbStatus status;

    if (rb->count == (uint8_t)RB_CAPACITY)
    {
        status = RB_ERROR_FULL;
    }
    else
    {
        rb->data[rb->tail] = value;
        rb->tail = (uint8_t)((rb->tail + 1U) % (uint8_t)RB_CAPACITY);
        rb->count = (uint8_t)(rb->count + 1U);
        status = RB_OK;
    }

    return status;
}

RbStatus rb_pop(RingBuffer *rb, uint8_t *out)
{
    RbStatus status;

    if (rb->count == 0U)
    {
        status = RB_ERROR_EMPTY;
    }
    else
    {
        *out = rb->data[rb->head];
        rb->head = (uint8_t)((rb->head + 1U) % (uint8_t)RB_CAPACITY);
        rb->count = (uint8_t)(rb->count - 1U);
        status = RB_OK;
    }

    return status;
}

RbStatus rb_peek(const RingBuffer *rb, uint8_t *out)
{
    RbStatus status;

    if (rb->count == 0U)
    {
        status = RB_ERROR_EMPTY;
    }
    else
    {
        *out = rb->data[rb->head];
        status = RB_OK;
    }

    return status;
}

uint8_t rb_count(const RingBuffer *rb)
{
    return rb->count;
}

bool rb_is_full(const RingBuffer *rb)
{
    bool result;

    if (rb->count == (uint8_t)RB_CAPACITY)
    {
        result = true;
    }
    else
    {
        result = false;
    }

    return result;
}

bool rb_is_empty(const RingBuffer *rb)
{
    bool result;

    if (rb->count == 0U)
    {
        result = true;
    }
    else
    {
        result = false;
    }

    return result;
}
```

Notable properties:

- **No dynamic memory.** Fixed-size `data[RB_CAPACITY]` array on the struct.
- **Single exit point per function.** Every function has exactly one `return`
  statement (Rule 15.5 satisfied by construction).
- **Fixed-width types throughout.** `uint8_t` for all index and count fields.
  Integer literals suffixed `U` or cast to `uint8_t` to match operand types.
- **No standard I/O.** No `printf`, no `<stdio.h>`.
- **All functions declared before use** via the header.

---

## What the Loop Did

The generator produced correct code on iteration 1 — all 33 tests passed. But
MISRA Rule 10.4 flagged the type mismatch between `uint8_t` indices and the
bare `int` constant `RB_CAPACITY` in modulo expressions.

This is exactly the class of defect MISRA targets in embedded C: arithmetic
that is semantically correct at runtime but violates the essential type system
that prevents implicit promotion hazards on constrained hardware.

The reprompt gave the LLM the rule ID, the rule text, and the five line numbers.
No test source. No assertions. Just what violated compliance and where. The fix
was a single consistent cast — `(uint8_t)RB_CAPACITY` — applied at every
modulo site.

**Iteration 1:** correct code, non-compliant. Score 0.30.
**Iteration 2:** correct code, compliant. Score 1.00. CONVERGED.

The loop is the product. The scorer is the standard. The generator fixes what
the scorer finds.
