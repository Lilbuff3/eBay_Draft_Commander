"""Price-discovery mode for no-comp items.

Commercial parts and other niche items often have zero recent eBay comps but
real value. Instead of stalling those jobs in pending_review, the processor
lists them HIGH — the web-research price range's high end when available,
else suggested * (1 + markup) — with Best Offer enabled and an aggressive
markdown ladder tag, letting the market discover the price.

Pure functions only; the processor seam lives in processor_service.
"""
from typing import Any, Optional

# Sources whose price came from AI/web research with no eBay comps behind it.
# market_ai_conflict is deliberately excluded: comps exist there (just in
# disagreement with AI) and that fight belongs in the Review Queue.
DISCOVERY_SOURCES = frozenset({
    'ai_grounded_research',
    'research_market_price',
    'ai_estimate',
})


def is_discovery_eligible(pricing_result: dict, enabled: bool) -> bool:
    """A job qualifies for price discovery when the feature is on, the price
    came from a no-comp AI/research source, and there are no comps at all."""
    if not enabled:
        return False
    if pricing_result.get('comps'):
        return False
    return pricing_result.get('source') in DISCOVERY_SOURCES


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute_discovery_price(pricing_result: dict, ai_data: Optional[dict],
                            markup_pct: float) -> Optional[dict]:
    """Pick the discovery list price: max(research-range high, suggested*(1+markup)).

    Returns {'list_price': float, 'basis': 'research_high'|'markup'} or None
    when no positive price can be produced (job stays in review).
    """
    suggested = _to_float(pricing_result.get('price'))
    markup_price = round(suggested * (1 + markup_pct / 100), 2) if suggested > 0 else 0.0

    research_high = 0.0
    if isinstance(ai_data, dict):
        market = (ai_data.get('research') or {}).get('market_price') or {}
        if isinstance(market, dict):
            research_high = _to_float(market.get('high'))

    if research_high <= 0 and markup_price <= 0:
        return None
    if research_high > markup_price:
        return {'list_price': round(research_high, 2), 'basis': 'research_high'}
    return {'list_price': markup_price, 'basis': 'markup'}
