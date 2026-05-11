# ReportService — Test Goals

## `summarize`

- Returns the correct format string for each of the four order statuses (CONFIRMED, PENDING, FAILED, CANCELLED)
- The CONFIRMED format includes the item count
- The PENDING format includes the "awaiting confirmation" suffix
- The order_id appears verbatim in all output strings
- Raises `ReportError` when `order_id` is an empty string
- Handles an order with zero items without crashing (CONFIRMED format shows "0 item(s)")

## `validate`

- Returns `True` for a well-formed request (non-empty order_id, non-empty items list, all quantities positive, all ingredient names non-empty)
- Returns `False` when `order_id` is empty
- Returns `False` when `items` is an empty list
- Returns `False` when any item has `quantity` of zero
- Returns `False` when any item has `quantity` less than zero
- Returns `False` when any item has an empty `ingredient` string
- Returns `False` on the first invalid item even when other items are valid
- Never raises — all invalid inputs produce `False`

## `compute_totals`

- Returns a dict mapping ingredient names to total quantities
- Correctly sums multiple items with the same ingredient name
- Returns each ingredient exactly once in the result dict
- Raises `ReportError` when called with an empty list
- Raises `ReportError` when any item has `quantity <= 0`
- Handles a single-item list correctly
- Handles items with distinct ingredient names (no summing needed)
