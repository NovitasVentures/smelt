# CoffeeLoop System — Implementation Spec

Implement the three core CoffeeLoop service components as a single Python module named
`coffeeloop`. The module must satisfy the CoffeeLoop Software Architecture Document
(SAD, ISO/IEC/IEEE 42010:2011).

---

## Dependencies

The `coffeeloop_core` package is installed and provides all shared domain types.
**Do not define these types locally.** Import them:

```python
from coffeeloop_core import Order, OrderItem, OrderStatus, ServiceResponse
from coffeeloop_core.exceptions import OrderError, InventoryError, NotificationError
```

Any locally defined version of `Order`, `ServiceResponse`, `OrderError`,
`InventoryError`, or `NotificationError` is a violation of the System-Wide DRY
principle (SAD Section 6.2).

---

## Architectural Constraints (from the SAD)

All code in this module must satisfy three architectural principles:

### 1. Single Exit Path (SAD Section 6.1)
Every function must have **exactly one `return` statement**, at the final line.
- Initialize a result variable at the top.
- Modify it through the logic.
- Return it exactly once at the end.
- No early returns. No `return` inside `if` branches.

### 2. System-Wide DRY — Shared Core (SAD Section 6.2)
All shared types (`Order`, `OrderStatus`, `ServiceResponse`, `OrderError`,
`InventoryError`, `NotificationError`) must be imported from `coffeeloop_core`.
Never define them inline.

### 3. Structured Exception Handling (SAD Section 6.3)
- Use specific `try...except` blocks for expected failures.
- Always re-wrap low-level exceptions into a standard `coffeeloop_core` exception
  before propagating. Never let raw Python errors escape a service boundary.
- The `OrderGateway.process_order` method is a service boundary and must have a
  top-level `try...except` that wraps all failures into `OrderError`.

---

## Component 1 — `InventoryManager`

Manages ingredient stock. Maintains state internally (a dict of ingredient → quantity).

### `InventoryManager.__init__(self, stock: dict[str, int])`
Initialize with initial stock levels.

### `InventoryManager.check_availability(self, items: list[OrderItem]) -> bool`
Returns `True` if all items can be fulfilled from current stock, `False` otherwise.
Raises `InventoryError` if `items` is empty.

### `InventoryManager.reserve(self, items: list[OrderItem]) -> None`
Deducts the quantities in `items` from the internal stock.
Raises `InventoryError` if stock is insufficient for any ingredient (check before deducting).
Idempotent: if a reservation is impossible, stock must be unchanged.

---

## Component 2 — `NotificationService`

Translates order events into human-readable messages. Stateless.

### `NotificationService.dispatch(self, order_id: str, status: OrderStatus) -> str`
Formats and returns a notification message string for the given order status.
Raises `NotificationError` if `order_id` is empty or `status` is not a valid `OrderStatus`.

---

## Component 3 — `OrderGateway`

The central orchestrator. Manages the order lifecycle from submission to notification.

### `OrderGateway.__init__(self, inventory: InventoryManager, notifications: NotificationService)`
Accepts the two dependent services.

### `OrderGateway.process_order(self, order_id: str, items: list[OrderItem]) -> ServiceResponse`
Orchestrates the full order lifecycle:

1. Validate that `items` is non-empty.
2. Call `self.inventory.check_availability(items)` to verify stock.
3. If available: call `self.inventory.reserve(items)` to commit the reservation.
4. Create an `Order` object (imported from `coffeeloop_core`) with status `CONFIRMED`.
5. Call `self.notifications.dispatch(order_id, OrderStatus.CONFIRMED)`.
6. Return a `ServiceResponse(success=True, order=order)`.

Error handling (per SAD Section 6.3):
- Wrap `InventoryError` (from check or reserve) into `OrderError` and re-raise.
- If notification fails: the order is already confirmed. Log the failure (use
  `logging.warning`), do not raise — return `ServiceResponse(success=True, order=order)`.
- Wrap any other unexpected exception into `OrderError` and re-raise.

The function must follow the Single Exit Path principle: one `return` at the end.

---

## Module-Level Setup

Include at the top of the module:
```python
import logging
log = logging.getLogger(__name__)
```

No `print()` statements. Use `log.warning()` for non-fatal events.
