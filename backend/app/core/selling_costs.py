"""What eBay takes, and what's left.

One formula for fees. It was written six ways -- jobs_api, ledger, sourcing,
pricing_engine twice, and frontend/src/lib/fees.ts -- and the copies had
already drifted on which shipping number counts as a cost.

ship_cost() is deliberately SOURCING_SHIP_COST, not ESTIMATED_SHIPPING_COST:
the latter is a buffer added to the *list price* under free shipping, not what
the parcel costs you. A caller that means something else passes its own.
"""
from typing import Optional

from backend.app.core.constants import (
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
)

DEFAULT_SHIP_COST = 5.00


def fees(amount: float) -> float:
    """eBay's cut on a sale of `amount`: final value fee + payment processing.

    Zero or missing amount means no sale, so no fees -- a $0 order must not
    report the $0.30 processing fee.
    """
    if not amount or amount <= 0:
        return 0.0
    return amount * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE


def ship_cost() -> float:
    """What a parcel actually costs you. Live-read so Settings applies at once."""
    from backend.app.core.settings_manager import get_settings_manager
    try:
        return float(get_settings_manager().get(
            'SOURCING_SHIP_COST', str(DEFAULT_SHIP_COST)))
    except (TypeError, ValueError):
        return DEFAULT_SHIP_COST


def net(amount: float, ship: Optional[float] = None, cogs: float = 0.0) -> float:
    """What's left of `amount` after eBay's cut, shipping and cost of goods.

    ship=None reads the knob. Pass it explicitly to keep a caller pure.
    """
    if not amount or amount <= 0:
        return 0.0
    if ship is None:
        ship = ship_cost()
    return amount - fees(amount) - ship - (cogs or 0.0)
