# CoffeeLoop Test Goals

## InventoryManager

- `check_availability` returns `True` when all requested ingredients are in stock
- `check_availability` returns `False` when any ingredient has insufficient quantity
- `check_availability` raises `InventoryError` when called with an empty items list
- `reserve` deducts quantities from stock when items are available
- `reserve` raises `InventoryError` when stock is insufficient for any ingredient
- `reserve` leaves stock unchanged when it raises (idempotent on failure)

## NotificationService

- `dispatch` returns a non-empty string message for a confirmed order
- `dispatch` returns a non-empty string message for a failed order
- `dispatch` raises `NotificationError` when called with an empty order_id

## OrderGateway — Happy Path

- `process_order` returns `ServiceResponse(success=True)` when items are available
- The returned `ServiceResponse.order` is an `Order` instance from `coffeeloop_core`
- The returned order has status `OrderStatus.CONFIRMED`
- The returned order contains the items passed to `process_order`
- Stock is reduced after a successful `process_order`

## OrderGateway — Error Handling

- `process_order` raises `OrderError` when inventory is insufficient (wraps `InventoryError`)
- `process_order` raises `OrderError` when called with an empty items list
- `process_order` completes successfully even when notification dispatch fails
  (notification failure is non-fatal: order is confirmed, no exception raised)

## Type Integrity

- All exceptions raised by `OrderGateway` are instances of `OrderError` (from `coffeeloop_core`)
- `ServiceResponse` returned is an instance of `coffeeloop_core.ServiceResponse`
- `Order` in the response is an instance of `coffeeloop_core.Order`
