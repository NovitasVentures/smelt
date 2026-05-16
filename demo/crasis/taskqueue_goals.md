# TaskQueue Test Goals

## Construction

- A `TaskQueue` constructed with capacity 1 accepts one order and rejects a second
- A `TaskQueue` constructed with capacity 0 raises `ValueError`
- A `TaskQueue` constructed with capacity 5 reports `size()` of 0 initially

## enqueue

- Enqueuing an order increases `size()` by 1
- Enqueuing a second order with the same `order_id` raises `OrderError`
- Enqueuing when the queue is at capacity raises `OrderError`
- Enqueuing an order with an empty `order_id` raises `OrderError`

## dequeue

- Dequeuing from a single-item queue leaves `size()` at 0
- Dequeuing removes the front order (FIFO: first enqueued is first removed)
- Dequeuing from an empty queue raises `OrderError`

## cancel

- Cancelling a queued order by `order_id` removes it from the queue
- Cancelling the middle order of three leaves the other two in original order
- Cancelling with an `order_id` not in the queue raises `OrderError`

## update_status

- After `update_status`, `find()` returns the order with the new status
- `update_status` with an `order_id` not in the queue raises `OrderError`

## peek

- `peek` returns the front order without changing `size()`
- `peek` on an empty queue raises `OrderError`
- After `enqueue` then `dequeue`, `peek` returns the second-enqueued order

## find

- `find` returns the correct order regardless of its position in the queue
- `find` with an `order_id` not in the queue raises `OrderError`

## size / is_full / pending

- `size()` reflects the current count after a sequence of enqueue and dequeue operations
- `is_full()` returns `True` when `size()` equals `capacity`
- `is_full()` returns `False` after a dequeue brings the count below capacity
- `pending()` returns only orders with status `OrderStatus.PENDING`
- `pending()` returns an empty list when no orders are pending
- `pending()` preserves queue order among the returned orders
