# SOP: Price Research (`price_research.py`)

## Purpose
The `PriceResearcher` module provides market intelligence by fetching "Sold" listing data from eBay. It helps set competitive prices based on actual historical sales rather than just guesswork or current "Active" listings.

## Location
`tools/price_research.py`

## Logic

### 1. Market Search (`search_sold_items`)
- Uses the **eBay Browse API** (`/item_summary/search`).
- Filters for `buyingOptions:{FIXED_PRICE}`.
- Sorts by price to find the range.

### 2. Analysis (`analyze_prices`)
- Calculates:
  - **Average Price**: Mean of all results.
  - **Median Price**: The middle value (best for filtering outliers).
  - **Suggested Price**: Derived as 95% of the Median to ensure competitiveness.
- buckets results into a price distribution for visualization.

### 3. Quick Suggestion (`get_price_suggestion`)
- Simplifies a listing title into keywords.
- Performs research.
- Applies a **Condition Adjustment** multiplier:
  - New: 1.3x
  - Like New: 1.2x
  - Used - Good: 0.9x
  - For Parts: 0.4x

## Dependencies
- `EBAY_USER_TOKEN`: Browse API requires User-level authorization.
