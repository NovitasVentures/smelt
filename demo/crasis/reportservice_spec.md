# CoffeeLoop ReportService — Implementation Spec

Implement a single Python module named `reportservice` containing one class: `ReportService`.

---

## Dependencies

The `coffeeloop_core` package is installed and provides shared domain types:

```python
from coffeeloop_core import Order, OrderItem, OrderStatus
from coffeeloop_core.exceptions import ReportError
```

---

## `ReportService`

Stateless utility class. Generates human-readable order summaries and validates report
requests. Contains no instance state; all methods operate on their arguments.

### `ReportService.summarize(self, order: Order) -> str`

Returns a single-line summary string for the given order.

Format rules:
- If `order.status` is `CONFIRMED`: `"Order <order_id>: CONFIRMED — <n> item(s)"`
- If `order.status` is `PENDING`: `"Order <order_id>: PENDING — awaiting confirmation"`
- If `order.status` is `FAILED`: `"Order <order_id>: FAILED — no items reserved"`
- If `order.status` is `CANCELLED`: `"Order <order_id>: CANCELLED"`
- `order_id` is rendered as-is (no padding or truncation)
- `<n>` is `len(order.items)`

Raises `ReportError` if `order.order_id` is empty.

### `ReportService.validate(self, order_id: str, items: list[OrderItem]) -> bool`

Returns `True` if the report request is valid, `False` otherwise.

A request is valid when ALL of the following hold:
- `order_id` is a non-empty string
- `items` is non-empty
- Every `OrderItem` has `quantity > 0`
- Every `OrderItem.ingredient` is a non-empty string

Returns `False` for any violation of the above. Does not raise.

### `ReportService.compute_totals(self, items: list[OrderItem]) -> dict[str, int]`

Returns a dict mapping each ingredient name to its total quantity across all items.
Items with the same ingredient name are summed.

Raises `ReportError` if `items` is empty.
Raises `ReportError` if any `OrderItem.quantity` is not a positive integer (i.e., `<= 0`).

---

## Module-Level Setup

```python
import logging
log = logging.getLogger(__name__)
```

No `print()` statements.
