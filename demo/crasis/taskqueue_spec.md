# TaskQueue — Implementation Spec

Implement a single Python module named `taskqueue` containing one class: `TaskQueue`.

---

## Dependencies

The `coffeeloop_core` package is installed and provides shared domain types:

```python
from coffeeloop_core import Order, OrderItem, OrderStatus
from coffeeloop_core.exceptions import OrderError
```

Type signatures (use these exactly — do not redefine):

```python
@dataclass
class OrderItem:
    ingredient: str   # non-empty string name of the ingredient
    quantity: int     # number of units

@dataclass
class Order:
    order_id: str
    items: list[OrderItem]
    status: OrderStatus = OrderStatus.PENDING

class OrderStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
```

---

## `TaskQueue`

Stateful work queue for pending orders. Holds orders that have been submitted but
not yet processed. All instance state is private.

### Constructor

```python
TaskQueue(capacity: int)
```

`capacity` is the maximum number of orders the queue may hold simultaneously.
Raises `ValueError` if `capacity` is less than 1.

---

### Commands (mutate state, return None)

#### `TaskQueue.enqueue(self, order: Order) -> None`

Adds `order` to the back of the queue.

- Raises `OrderError` if the queue is already at capacity.
- Raises `OrderError` if `order.order_id` is empty.
- Raises `OrderError` if an order with the same `order_id` is already in the queue.

#### `TaskQueue.dequeue(self) -> None`

Removes the order at the front of the queue.

- Raises `OrderError` if the queue is empty.

#### `TaskQueue.cancel(self, order_id: str) -> None`

Removes the order with the given `order_id` from the queue, regardless of its
position.

- Raises `OrderError` if no order with that `order_id` exists in the queue.

#### `TaskQueue.update_status(self, order_id: str, status: OrderStatus) -> None`

Sets the `status` field of the order with the given `order_id` to `status`.

- Raises `OrderError` if no order with that `order_id` exists in the queue.

---

### Queries (read state, no side effects)

#### `TaskQueue.peek(self) -> Order`

Returns the order at the front of the queue without removing it.

- Raises `OrderError` if the queue is empty.

#### `TaskQueue.find(self, order_id: str) -> Order`

Returns the order with the given `order_id`.

- Raises `OrderError` if no order with that `order_id` exists in the queue.

#### `TaskQueue.size(self) -> int`

Returns the number of orders currently in the queue.

#### `TaskQueue.is_full(self) -> bool`

Returns `True` if the number of orders equals `capacity`, `False` otherwise.

#### `TaskQueue.pending(self) -> list[Order]`

Returns a list of all orders whose `status` is `OrderStatus.PENDING`, in
queue order (front first). Returns an empty list if none exist.

---

## Module-Level Setup

```python
import logging
log = logging.getLogger(__name__)
```

No `print()` statements.
