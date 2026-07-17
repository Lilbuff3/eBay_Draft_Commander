"""Stale-item markdown ladder math. Pure — no eBay, no settings, no clock.

The autopilot scanner decides WHEN to call this; this module only answers
"given the knobs, what's the next price?" so the money math stays trivially
unit-testable.
"""
from typing import Optional


def compute_markdown(original_price, current_price, days_live, *,
                     after_days, step_pct, floor_pct) -> Optional[float]:
    """Next ladder price, or None when no markdown is due.

    - Not due until the listing has been live >= after_days.
    - Each step drops step_pct% off the CURRENT price (compounding).
    - Never returns below original_price * floor_pct/100; at/below the floor
      the ladder is done (idempotent — repeated calls keep returning None).
    """
    try:
        original = float(original_price)
        current = float(current_price)
        days = float(days_live)
        after = float(after_days)
        step = float(step_pct)
        floor_ratio = float(floor_pct)
    except (TypeError, ValueError):
        return None
    if original <= 0 or current <= 0 or step <= 0:
        return None
    if days < after:
        return None
    floor = round(original * floor_ratio / 100, 2)
    if current <= floor:
        return None
    new_price = round(current * (1 - step / 100), 2)
    if new_price < floor:
        new_price = floor
    if new_price >= current:
        return None
    return new_price
