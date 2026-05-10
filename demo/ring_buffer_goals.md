# Ring Buffer Test Goals

## Initialization
- After rb_init, rb_count returns 0
- After rb_init, rb_is_empty returns true
- After rb_init, rb_is_full returns false

## Push behavior
- rb_push on an empty buffer returns RB_OK
- rb_push increases rb_count by exactly 1
- rb_push on a full buffer (count == RB_CAPACITY) returns RB_ERROR_FULL
- rb_push on a full buffer does not change rb_count
- After pushing RB_CAPACITY elements, rb_is_full returns true

## Pop behavior
- rb_pop on an empty buffer returns RB_ERROR_EMPTY
- rb_pop on an empty buffer does not write to the output pointer
- rb_pop on a non-empty buffer returns RB_OK
- rb_pop writes the correct element value to the output pointer
- rb_pop decreases rb_count by exactly 1
- After popping all elements, rb_is_empty returns true

## FIFO ordering
- Elements are returned in push order: push 1, push 2, push 3 → pop returns 1, then 2, then 3
- Partial drain and refill: fill completely, pop half, push half → FIFO order is preserved across the wrap-around boundary

## Peek behavior
- rb_peek on an empty buffer returns RB_ERROR_EMPTY
- rb_peek on an empty buffer does not write to the output pointer
- rb_peek on a non-empty buffer returns RB_OK
- rb_peek writes the correct element value to the output pointer
- rb_peek does not change rb_count
- rb_peek returns the same element that rb_pop would return next

## Boundary conditions
- Single-element buffer operation: push one element, then pop returns that element
- Full capacity push/pop cycle: fill to RB_CAPACITY, pop all elements, push RB_CAPACITY again — all operations return RB_OK and values are correct
- Index wrap-around: pushing and popping across the RB_CAPACITY boundary produces correct values (head and tail indices wrap using modulo correctly)
