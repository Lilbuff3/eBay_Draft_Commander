"""Profit ledger — local sales snapshots + real net profit math.

Sales rows accumulate in SQLite (past eBay's 90-day order window) via an
upsert sweep piggybacked on every /api/orders fetch. COGS comes from
job_metadata['cogs'] (WhatsApp caption, item edit, or sourcing flow) and is
frozen onto the sale row; unknown COGS is a first-class state (net = None).

Fee estimate reuses the same constants as sourcing.compute_verdict:
    fees = sale_total * FVF_RATE + payment_fee
    net  = sale_total - fees - ship_est - cogs
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.constants import (
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
)
from backend.app.core.logger import get_logger

logger = get_logger('services.ledger')


def _setting_float(key: str, default: float) -> float:
    from backend.app.core.settings_manager import get_settings_manager
    try:
        return float(get_settings_manager().get(key, str(default)))
    except (TypeError, ValueError):
        return default


def estimate_net(sale_total: float, cogs: Optional[float] = None,
                 ship_cost: Optional[float] = None) -> Dict[str, Any]:
    """Fee/net estimate for one sale. cogs=None -> net=None (unknown, not zero)."""
    if ship_cost is None:
        ship_cost = _setting_float('SOURCING_SHIP_COST', 5.0)
    fees = sale_total * EBAY_FINAL_VALUE_FEE_RATE + EBAY_PAYMENT_PROCESSING_FEE
    net = None
    if cogs is not None:
        net = sale_total - fees - ship_cost - cogs
    return {
        'fees_est': round(fees, 2),
        'ship_est': round(ship_cost, 2),
        'net': round(net, 2) if net is not None else None,
    }
