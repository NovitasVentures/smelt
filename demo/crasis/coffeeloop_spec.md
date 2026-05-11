# CoffeeLoop System — Implementation Spec

Implement the three core CoffeeLoop service components as a single Python module named
`coffeeloop`.

---

## Dependencies

The `coffeeloop_core` package is installed and provides shared domain types:

```python
from coffeeloop_core import Order, OrderItem, OrderStatus, ServiceResponse
from coffeeloop_core.exceptions import OrderError, InventoryError, NotificationError
```

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
Raises `InventoryError` if stock is insufficient for any ingredient.
If a reservation is impossible, stock must remain unchanged.

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
2. Check availability via `self.inventory.check_availability(items)`.
3. If available: reserve via `self.inventory.reserve(items)`.
4. Create an `Order` (from `coffeeloop_core`) with status `CONFIRMED`.
5. Dispatch a notification via `self.notifications.dispatch(order_id, OrderStatus.CONFIRMED)`.
6. Return a `ServiceResponse(success=True, order=order)`.

Error handling:
- `InventoryError` from check or reserve must surface as `OrderError`.
- If notification fails: the order is already confirmed. Log the failure with
  `logging.warning`, do not raise — return `ServiceResponse(success=True, order=order)`.
- Any other unexpected exception must surface as `OrderError`.

---

## Module-Level Setup

```python
import logging
log = logging.getLogger(__name__)
```

No `print()` statements. Use `log.warning()` for non-fatal events.
