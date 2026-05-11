"""CoffeeLoop shared core — canonical types for all CoffeeLoop services.

Per the CoffeeLoop Architecture Document (SAD Section 6.2), all services must
import their domain types from this package rather than defining them locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from coffeeloop_core.exceptions import InventoryError, NotificationError, OrderError

__all__ = [
    "Order",
    "OrderItem",
    "OrderStatus",
    "ServiceResponse",
    "OrderError",
    "InventoryError",
    "NotificationError",
]


class OrderStatus(Enum):
    """Lifecycle states of an order."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderItem:
    """A single item within an order."""

    ingredient: str
    quantity: int


@dataclass
class Order:
    """Canonical order domain object."""

    order_id: str
    items: list[OrderItem]
    status: OrderStatus = OrderStatus.PENDING


@dataclass
class ServiceResponse:
    """Standard response envelope for all CoffeeLoop service calls."""

    success: bool
    order: Order | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)
