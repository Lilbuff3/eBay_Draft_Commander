# Pricing-Accuracy Audit — 2026-06-26

Audit of the pricing engine for revenue/sell-through impact. Pricing is the
single highest-$ lever in the app: too high → dead inventory; too low → money
left on the table every sale.

Scope: `backend/app/services/pricing_engine.py`, `ebay/researcher.py`,
`ebay/browse.py`, `core/constants.py`.

## TL;DR

The cascade is well-built (median, rarity 75th pctl, same-grade condition
matching, fee-aware margin, .99 rounding). **But every market-data comp is an
ACTIVE asking price, not a SOLD price** — which systematically overprices and
hurts sell-through. That is the #1 fix. Everything else is secondary.

## Findings (ranked by $ impact)

### 1. CRITICAL — Comps are active asking prices, not sold prices
All four market-data strategies (ISBN, MPN/model, alt part numbers, keyword) in
`get_price_with_comps` call `search_sold_listings` →
`ebay/researcher.py:search_sold` → **Browse API = active listings**
(`researcher.py:4`: "Primary: eBay Browse API (condition-filtered active
listings)"). The method name is a misnomer.

Why it matters: the median of *active* asking prices is systematically **higher**
than actual sold prices — overpriced items linger in active listings while the
ones that sold cheap are already gone. Net effect: the engine **overprices**,
which slows sell-through and grows dead inventory (capital tied up = pure loss).

eBay no longer exposes true sold/completed data via the standard Browse API
(legacy Finding API `findCompletedItems` is deprecated; the **Marketplace
Insights API** has sold data but is access-gated by eBay approval).

**Fixes:**
- **(a) Primary, do now — `ACTIVE_TO_SOLD_FACTOR`.** Apply a configurable
  discount to `base_price` in `calculate_suggested_price` before it becomes the
  suggested price. Env-tunable (start ~0.85–0.90). Blunt but corrects the
  systematic bias on every comp-based sale. Apply BEFORE the shipping buffer and
  margin checks.
- **(b) Calibrate it from real data.** The app already logs outcomes to
  `data/listing_results.jsonl` (`results_logger.py`). Compare suggested price vs
  actual sale price over time to tune the factor per category instead of one
  global guess.
- **(c) Stretch — Marketplace Insights API.** Pursue eBay approval for true sold
  data. The "correct" source, but gated + higher effort.
- **(d) Cleanup — rename** `search_sold`/`search_sold_listings` →
  `search_active_comps` so the data source stops hiding behind a misleading name.

### 2. MEDIUM — Margin floor is disabled when acquisition_cost = 0
`calculate_suggested_price` margin protection (line ~302) only triggers
`if acquisition_cost > 0`. A reseller who doesn't enter cost-of-goods gets **no
margin-aware floor** at all — only the flat `MIN_LISTING_PRICE` / `DEFAULT_MIN_PRICE`.

**Fix:** support an optional `DEFAULT_ACQUISITION_COST` env, or a category-based
absolute floor, so margin protection isn't silently off in the common case.

### 3. LOW-MED — `MIN_LISTING_PRICE = 4.99` is flat, below some eBay minimums
`constants.py:86`. Some categories enforce higher fixed-price minimums; a flat
$4.99 can yield rejected or too-low listings. **Fix:** category-aware minimum, or
raise the floor.

### 4. MEDIUM — No Best Offer (covered by the Offers work order)
Listings don't enable Best Offer. Enabling it with auto-accept/decline thresholds
captures price-sensitive buyers and yields real market signal. Tracked in
`GEMINI_OFFERS_MARKDOWNS.md`.

### 5. LOW — `filter_comps` tuning
Title-similarity threshold is 30% word overlap (loose; lets loosely-related items
in) and outlier rejection only runs at ≥5 comps. With active comps already noisy
(Finding 1), this compounds. **Fix:** raise similarity, apply outlier rejection
at ≥4.

### What's already good (keep)
Median (outlier-robust) · 75th percentile for rare/very_rare · same-grade
condition matching (`prefer_same_grade_comps`, ≥4 matches) · fee-aware margin calc
(13.25% + $0.30) · smart .99 rounding · NaN/bounds sanitize · loud-fail cascade.

## Recommended order of work
1. **Finding 1(a) — `ACTIVE_TO_SOLD_FACTOR`** (surgical, highest certainty, biggest $).
2. Finding 1(d) rename + Finding 5 tuning (cheap cleanups, same PR).
3. Finding 2 margin-floor-at-zero-cost.
4. Finding 1(b) calibration tooling from `listing_results.jsonl`.
5. Finding 1(c) Marketplace Insights (stretch, needs eBay approval).

## Open decision for the owner
Finding 1(a) needs a starting factor. Options: a single global `0.87`, or
category-varying. Recommend: ship a global `0.87` env default now, then calibrate
from `listing_results.jsonl` (Finding 1b). Implementation is mine (needs judgment
on the live cascade) — pending the factor decision.
