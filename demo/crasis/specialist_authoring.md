# Crasis Specialist Authoring — Lessons from Demo 6

This document captures the process for writing `eval_on` examples in Crasis specialist specs.
Getting this right the first time avoids repeated `crasis build` runs, which are expensive at
scale (3000 synthetic samples per build, each requiring API calls to generate).

---

## The core problem: eval_on drives everything

The `eval_on` examples in a spec are not just a quality gate — they are the **seeds for all
3000 synthetic training samples**. The LLM generating training data can only extrapolate from
what it sees in `eval_on`. Any method shape not represented in `eval_on` will be either absent
from the training set or represented inconsistently.

A missing pattern means the specialist either:
- **False positives**: fires on a legitimate pattern that looks structurally similar to a
  violation (e.g., a query that iterates `self.*` looks like a command that mutates and returns)
- **False negatives**: misses a violation variant it has never seen

Both failures force a rebuild. At 3000 samples and API cost per sample, each rebuild is
non-trivial. At larger volumes (10k–50k) it becomes a meaningful budget item.

---

## The spec-first authoring process

Before writing a single `eval_on` example, enumerate every method shape the target code will
contain. For each method, classify it explicitly. Then write an `eval_on` example for every
distinct shape.

### Step 1 — List every method the generated code will have

Write out the full method inventory from the spec:

```
enqueue(order) -> None        # command: appends to queue, adds to id set
dequeue() -> None             # command: popleft from queue, removes from id set
cancel(order_id) -> None      # command: del from queue by index, remove from id set
update_status(id, status)     # command: attribute assignment on found item
peek() -> Order               # query: returns queue[0], no mutation
find(order_id) -> Order       # query: iterates queue, returns matching item
size() -> int                 # query: returns len()
is_full() -> bool             # query: returns comparison
pending() -> list[Order]      # query: list comprehension over queue
```

### Step 2 — Classify each method

For each method, ask three questions:
1. Does it assign to, append to, remove from, or delete from any `self.*` attribute? → **command**
2. Does it return a value (not None, not self, not bare return)? → **query**
3. Does it do BOTH? → **violation**

Flag any method that is structurally similar to a violation but is not one. These are your
highest-risk false-positive candidates and need the most explicit coverage.

### Step 3 — Write eval_on examples for every distinct structural shape

Group by shape, not by method name. The shapes that matter:

| Shape | Class | Example |
|---|---|---|
| Command: appends + adds to set | Clean | `enqueue` |
| Command: popleft + remove | Clean | `dequeue` |
| Command: for-loop, del by index, bare return | Clean | `cancel` |
| Command: for-loop, attribute assignment, bare return | Clean | `update_status` |
| Query: returns collection[0] | Clean | `peek` |
| Query: for-loop, returns matching item | Clean | `find` — **HIGH RISK FP** |
| Query: list comprehension over self.* | Clean | `pending` — **HIGH RISK FP** |
| Query: returns len() | Clean | `size` |
| Query: returns comparison | Clean | `is_full` |
| Command-returns-value: appends + returns stored item | Violation | `enqueue` returning order |
| Command-returns-value: popleft + remove + returns item | Violation | `dequeue` returning order |
| Command-returns-value: for-loop + del + returns item | Violation | `cancel` returning order |
| Command-returns-value: mutates attribute + returns it | Violation | `reserve` |
| Command-returns-value: mutates in loop + returns count | Violation | `add_all` returning len |

**Mark HIGH RISK FP shapes explicitly.** These are shapes where the classifier is most likely
to confuse a clean method with a violation because they share structural tokens with violations.

### Step 4 — Write the high-risk FP examples first

High-risk false positives are shapes where a clean method:
- Iterates a `self.*` collection (like a violation does)
- Returns something (like a violation does)
- But does NOT mutate self

For CQS, the high-risk FP shapes are queries that loop over or index `self.*`:

```yaml
- "def find(self, order_id: str) -> Order:\n    for order in self._queue:\n        if
  order.order_id == order_id:\n            return order\n    raise OrderError('not found')
  # Correct query - iterates self._queue but does not mutate it"
- "def pending(self) -> list[Order]:\n    return [order for order in self._queue if
  order.status == OrderStatus.PENDING]  # Correct query - list comprehension over
  self._queue, no mutation"
```

Write these as negative examples (clean code) with explicit comments explaining WHY they
are clean despite looking similar to violations.

### Step 5 — Write violation examples that mirror the high-risk FP shapes

For every high-risk FP shape, write a corresponding violation that differs by exactly one
element — the mutation. This trains the model to key on the presence/absence of mutation,
not on the structural shape:

```yaml
# Clean: iterates self._queue, returns item, no mutation
- "def find(self, order_id) -> Order:\n    for order in self._queue:\n        if ...\n
  return order  # Correct query"

# Violation: same iteration pattern, but also deletes from self before returning
- "def cancel(self, order_id) -> Order:\n    for i, order in enumerate(self._queue):\n
  if order.order_id == order_id:\n            del self._queue[i]\n
  self._order_ids.remove(order_id)\n            return order  # Violation - mutates then returns"
```

The minimal pair teaches the model that the distinguishing feature is the mutation, not the
for-loop or the return.

---

## Red flags during verification

Run `crasis classify` on every method in the method inventory before running the demo.
If any clean method scores above 0.80 on a 0.90 threshold, treat it as a build failure
and add more negative examples before running `smelt run`.

Signs you need more examples:
- A query that iterates `self.*` scores high (> 0.80) → add more filter/search query negatives
- A command with a bare `return` in a loop scores high → add more bare-return-in-loop negatives
- A violation scores below 0.85 → add more examples of that specific mutation pattern

---

## Threshold selection

The `confidence_threshold` in the profile is not arbitrary. Choose it by running the method
inventory through `crasis classify` and finding the threshold that:
- All violations score ABOVE it
- All clean methods score BELOW it

If no single threshold satisfies both, the spec needs more examples. Do not paper over a
bad specialist with a threshold tuned to your test set — the LLM will generate variants
you haven't tested and the threshold won't hold.

A specialist that achieves clean separation at 0.90 is production-ready.
A specialist that requires 0.75 to catch violations while also allowing FPs at 0.80 is not.

---

## Cost discipline

Each `crasis build` at 3000 samples costs roughly:
- 3000 API calls to generate synthetic training data
- ~10 minutes of local GPU time to train
- ~1 minute to export to ONNX

Rebuilds are paid entirely by the synthetic data generation step — training is cheap.

To avoid paying for rebuilds:
1. Complete the method inventory and eval_on authoring before the first build
2. Run the verification suite (step above) on a PREVIOUS specialist if one exists, or manually
   classify each shape against the spec description before building
3. Treat the first build as a "draft" — run verification, fix gaps, then build once more as
   the "production" specialist
4. Never run `smelt run` against an unverified specialist — a bad specialist oscillates the
   loop indefinitely (as in Demo 6, builds 1–3) which wastes LLM generation budget on top
   of the build cost

The minimum for a production-ready specialist: 2 builds (draft + verified). Budget for 3
if the principle has complex edge cases. If you're on build 4+, the `trigger`/`ignore`
language needs to be rewritten, not patched with more examples.

---

## Demo 6 build history (reference)

| Build | Root cause | Fix |
|---|---|---|
| 1 | Bare `return` in loop flagged as violation | Added eval_on for bare-return-in-loop as clean |
| 2 | `find`/`pending` (iterate self.* + return) flagged as violation | Added eval_on for query-iteration as clean |
| 3 | `dequeue`/`cancel` returning removed item not detected | Added eval_on for remove-then-return as violation |
| 4 | `pending` list comprehension still borderline | Added more list-comprehension query negatives |

All four could have been avoided with a complete method inventory before build 1.
