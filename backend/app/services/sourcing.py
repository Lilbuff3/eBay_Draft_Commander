"""Sourcing verdict math — buy/pass decisions for field barcode scanning.

Turns comp stats into "pay up to $X" using the same fee/discount constants
as the listing pipeline. Deliberately conservative: median-based (never the
margin-protected or .99-rounded pipeline price), no rarity percentile.
"""
from typing import Any, Dict, List, Optional

from backend.app.core.constants import (
    ACTIVE_TO_SOLD_FACTOR,
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
)

DEFAULT_MIN_PROFIT = 5.00
DEFAULT_ROI_MULTIPLE = 3.0
DEFAULT_SHIP_COST = 5.00

# max_buy below this is not worth pulling out a wallet for
MIN_VIABLE_BUY = 1.00
# fewer comps than this = data too thin to trust the median
SOLID_COMP_COUNT = 4


def _setting_float(key: str, default: float) -> float:
    from backend.app.core.settings_manager import get_settings_manager
    try:
        return float(get_settings_manager().get(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_sourcing_settings() -> Dict[str, float]:
    """Live-read sourcing knobs from .env via SettingsManager."""
    return {
        'min_profit': _setting_float('SOURCING_MIN_PROFIT', DEFAULT_MIN_PROFIT),
        'roi_multiple': _setting_float('SOURCING_ROI_MULTIPLE', DEFAULT_ROI_MULTIPLE),
        'ship_cost': _setting_float('SOURCING_SHIP_COST', DEFAULT_SHIP_COST),
    }


def compute_verdict(
    median_price: Optional[float],
    comp_count: int,
    prices: Optional[List[float]] = None,
    min_profit: Optional[float] = None,
    roi_multiple: Optional[float] = None,
    ship_cost: Optional[float] = None,
    id_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive a BUY / THIN / PASS / NO_DATA verdict from comp stats.

        est_sold_value = median * ACTIVE_TO_SOLD_FACTOR
        assumed_list   = est_sold_value + ship_cost   (free-shipping listing)
        net_proceeds   = assumed_list * (1 - FVF) - payment_fee - ship_cost
        max_buy        = min(net - min_profit, net / roi_multiple), floored at 0

    Explicit min_profit/roi_multiple/ship_cost args bypass SettingsManager
    (keeps the function pure for tests).
    """
    if min_profit is None or roi_multiple is None or ship_cost is None:
        settings = get_sourcing_settings()
        min_profit = settings['min_profit'] if min_profit is None else min_profit
        roi_multiple = settings['roi_multiple'] if roi_multiple is None else roi_multiple
        ship_cost = settings['ship_cost'] if ship_cost is None else ship_cost

    if not comp_count or not median_price or median_price <= 0:
        return {
            'verdict': 'NO_DATA',
            'max_buy': None,
            'est_sold_value': None,
            'net_proceeds': None,
            'price_range': None,
            'confidence': None,
            'confidence_reason': 'No comparable listings found',
        }

    est_sold_value = median_price * ACTIVE_TO_SOLD_FACTOR
    assumed_list = est_sold_value + ship_cost
    net_proceeds = (
        assumed_list * (1 - EBAY_FINAL_VALUE_FEE_RATE)
        - EBAY_PAYMENT_PROCESSING_FEE
        - ship_cost
    )

    roi_cap = net_proceeds / roi_multiple if roi_multiple and roi_multiple > 0 else net_proceeds
    max_buy = max(0.0, min(net_proceeds - min_profit, roi_cap))

    valid_prices = [p for p in (prices or []) if p and p > 0]
    price_range = (
        {'low': round(min(valid_prices), 2), 'high': round(max(valid_prices), 2)}
        if valid_prices else None
    )

    if max_buy < MIN_VIABLE_BUY:
        verdict = 'PASS'
    elif comp_count < SOLID_COMP_COUNT:
        verdict = 'THIN'
    else:
        verdict = 'BUY'

    confidence, confidence_reason = assess_confidence(comp_count, valid_prices, id_type)

    return {
        'verdict': verdict,
        'max_buy': round(max_buy, 2),
        'est_sold_value': round(est_sold_value, 2),
        'net_proceeds': round(net_proceeds, 2),
        'price_range': price_range,
        'confidence': confidence,
        'confidence_reason': confidence_reason,
    }


# how many times the priciest comp can exceed the cheapest before comps are "noisy"
SPREAD_TIGHT = 3.0
SPREAD_LOOSE = 6.0


def assess_confidence(comp_count, valid_prices, id_type, match_quality=None):
    """Grade how much to trust the number: exact-ID + many + tight comps = high.

    'Match quality' is: is the identity guaranteed (a book's ISBN, which eBay
    listings reliably contain -> clean comps; or a model-number-gated keyword
    match from the pricing pipeline) vs a loose match (UPC often absent from
    listings; plain keyword overlap), how many comps came back, and how wide
    the price spread is. Returns (level, one-line reason).

    match_quality (optional, from PricingEngine.filter_comps meta):
      'model_gated'/'exact_id' -> identity-trusted like an ISBN;
      'floor_fallback' -> comps survived only via the safety floor, cap at low;
      'similar'/'small_set'/None -> neutral (original Source-tab behavior).
    """
    if match_quality == 'floor_fallback':
        return 'low', 'comps matched only weakly (kept by safety floor) — treat as a ballpark'

    is_identity = id_type == 'isbn' or match_quality in ('model_gated', 'exact_id')
    lo = min(valid_prices) if valid_prices else 0
    hi = max(valid_prices) if valid_prices else 0
    spread = (hi / lo) if lo > 0 else None
    tight = spread is not None and spread <= SPREAD_TIGHT
    loose = spread is not None and spread > SPREAD_LOOSE
    many = comp_count >= SOLID_COMP_COUNT

    if many and not loose:
        if tight or is_identity:
            if id_type == 'isbn':
                note = 'exact ISBN match'
            elif match_quality in ('model_gated', 'exact_id'):
                note = 'model-number match'
            else:
                note = 'tight comps'
            return 'high', f'{comp_count} comps, {note}'
        return 'medium', f'{comp_count} comps but prices vary'
    if comp_count >= 2 and not loose:
        return 'medium', f'only {comp_count} comps'
    if loose:
        return 'low', f'wide price spread (${lo:.0f}-${hi:.0f}) - comps may not match'
    return 'low', f'only {comp_count} comp{"s" if comp_count != 1 else ""} — too thin to trust'


# Back-compat alias (pre-pipeline name)
_assess_confidence = assess_confidence
