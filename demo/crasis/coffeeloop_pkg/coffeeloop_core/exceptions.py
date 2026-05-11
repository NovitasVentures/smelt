"""CoffeeLoop standard exception hierarchy.

Per SAD Section 6.3, all service boundary exceptions must be instances of
these types. Low-level errors must be re-wrapped before propagating.
"""


class CoffeeLoopError(Exception):
    """Base class for all CoffeeLoop system exceptions."""


class OrderError(CoffeeLoopError):
    """Raised when order processing fails at the Gateway boundary."""


class InventoryError(CoffeeLoopError):
    """Raised when inventory operations fail (insufficient stock, unavailable)."""


class NotificationError(CoffeeLoopError):
    """Raised when the Notification Service cannot deliver an event."""


class ReportError(CoffeeLoopError):
    """Raised when report generation fails (invalid input, unknown status)."""
