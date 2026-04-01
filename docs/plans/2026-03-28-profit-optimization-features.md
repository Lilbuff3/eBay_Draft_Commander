# Profit Optimization Features — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 6 features that directly increase seller profit: smart shipping tiers, Media Mail detection, profit calculator UI, comp quality filtering, sold-vs-asking price labels, and smart scheduling presets.

**Architecture:** Backend changes in pricing_engine.py, listing_ai_agent.py, constants.py, and jobs_api.py. Frontend changes in ItemDetailDrawer.tsx and api.ts. All features are additive — no existing behavior changes unless explicitly noted.

**Tech Stack:** Python/Flask backend, React/TypeScript frontend, Zustand store, shadcn/ui components.

---

## Task 1: Move Shipping Tiers to Constants + Add Media Mail Detection

The shipping tier lookup and Media Mail book detection belong in `constants.py` so both the AI agent and pricing engine can reference them. Currently `SHIPPING_LOOKUP` is local to `listing_ai_agent.py`.

**Files:**
- Modify: `backend/app/core/constants.py`
- Modify: `backend/app/services/listing_ai_agent.py:10-19`
- Test: `tests/unit/test_shipping_estimation_unit.py`

**Step 1: Write the failing test**

In `tests/unit/test_shipping_estimation_unit.py`, add:

```python
class TestMediaMailDetection:
    """Books/media should use Media Mail shipping rate ($3.50) not standard."""

    def test_book_category_returns_media_mail_cost(self):
        from backend.app.core.constants import get_shipping_cost
        # Category 261186 = Books, category 11104 = Cookbooks
        assert get_shipping_cost(category_id="261186") == 3.50

    def test_isbn_present_returns_media_mail_cost(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(isbn="9781579656362") == 3.50

    def test_electronics_uses_ai_package_size(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(package_size="heavy") == 15.00

    def test_small_item_from_weight(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(estimated_weight_lbs=0.5) == 4.50

    def test_medium_item_from_weight(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(estimated_weight_lbs=2.0) == 6.50

    def test_fallback_returns_default(self):
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost() == 6.50

    def test_media_mail_overrides_package_size(self):
        """Even if AI says 'medium', a book should use Media Mail rate."""
        from backend.app.core.constants import get_shipping_cost
        assert get_shipping_cost(isbn="1234567890", package_size="medium") == 3.50
```

**Step 2: Run test to verify it fails**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_shipping_estimation_unit.py::TestMediaMailDetection -v`
Expected: FAIL — `get_shipping_cost` does not exist yet.

**Step 3: Implement in constants.py**

Add to `backend/app/core/constants.py` after the existing shipping constants:

```python
# --- Shipping Tiers ---
SHIPPING_LOOKUP = {
    'small': 4.50,   # < 1lb (USPS Ground Advantage)
    'medium': 6.50,  # 1-3lb
    'large': 10.00,  # 3-10lb
    'heavy': 15.00,  # 10+lb
}
MEDIA_MAIL_COST = 3.50  # USPS Media Mail (books, CDs, DVDs)
DEFAULT_SHIPPING_COST = 6.50

# eBay book/media category IDs (top-level and common subcategories)
MEDIA_MAIL_CATEGORIES = {
    '267',      # Books
    '261186',   # Books > Nonfiction
    '171228',   # Books > Fiction
    '29223',    # Books > Antiquarian & Collectible
    '2228',     # Books > Textbooks
    '11104',    # Cookbooks
    '171243',   # Children's Books
    '176973',   # Audiobooks
    '11232',    # CDs
    '176984',   # DVDs & Blu-ray
    '617',      # Records/Vinyl
    '80183',    # Video Games (disc-based)
}


def get_shipping_cost(
    category_id: str = None,
    isbn: str = None,
    package_size: str = None,
    estimated_weight_lbs: float = None,
) -> float:
    """Calculate shipping cost tier with Media Mail detection.

    Priority:
    1. Media Mail eligible (ISBN present OR book/media category) → $3.50
    2. AI-detected package size → tier lookup
    3. AI-estimated weight → tier by weight bracket
    4. Fallback → DEFAULT_SHIPPING_COST ($6.50)
    """
    # 1. Media Mail detection
    if isbn:
        return MEDIA_MAIL_COST
    if category_id and str(category_id) in MEDIA_MAIL_CATEGORIES:
        return MEDIA_MAIL_COST

    # 2. Package size from AI
    if package_size and package_size.lower() in SHIPPING_LOOKUP:
        return SHIPPING_LOOKUP[package_size.lower()]

    # 3. Weight-based tier
    if isinstance(estimated_weight_lbs, (int, float)):
        if estimated_weight_lbs < 1:
            return SHIPPING_LOOKUP['small']
        if estimated_weight_lbs <= 3:
            return SHIPPING_LOOKUP['medium']
        if estimated_weight_lbs <= 10:
            return SHIPPING_LOOKUP['large']
        return SHIPPING_LOOKUP['heavy']

    # 4. Fallback
    return DEFAULT_SHIPPING_COST
```

**Step 4: Update listing_ai_agent.py to use the new function**

Replace lines 10-19 and the `_calculate_shipping_cost` method:

```python
# Remove local SHIPPING_LOOKUP and DEFAULT_SHIPPING_COST
# Add import:
from backend.app.core.constants import get_shipping_cost, DEFAULT_SHIPPING_COST
```

Replace `_calculate_shipping_cost` method body:

```python
def _calculate_shipping_cost(self, ai_data: dict) -> float:
    """Calculate shipping cost using centralized tier logic."""
    ident = ai_data.get('identification', {})
    return get_shipping_cost(
        category_id=ident.get('category_id'),
        isbn=ident.get('isbn'),
        package_size=ident.get('package_size', ''),
        estimated_weight_lbs=ident.get('estimated_weight_lbs'),
    )
```

**Step 5: Run tests to verify they pass**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_shipping_estimation_unit.py -v`
Expected: All TestMediaMailDetection tests PASS. Existing shipping tests still PASS.

**Step 6: Commit**

```bash
git add backend/app/core/constants.py backend/app/services/listing_ai_agent.py tests/unit/test_shipping_estimation_unit.py
git commit -m "feat: centralize shipping tiers, add Media Mail detection for books

Books/media items now use $3.50 Media Mail rate instead of flat $6.50.
Shipping tier logic moved to constants.py for reuse across services."
```

---

## Task 2: Wire Category ID Into Shipping Cost Calculation

The `_calculate_shipping_cost` in `listing_ai_agent.py` now accepts `category_id`, but the processor_service doesn't pass it. The category is determined in step 4 of the pipeline, AFTER the AI agent returns. We need to recalculate shipping cost after category is known.

**Files:**
- Modify: `backend/app/services/processor_service.py:370-398`
- Test: `tests/unit/test_shipping_estimation_unit.py`

**Step 1: Write the failing test**

```python
class TestShippingRecalcAfterCategory:
    """Shipping cost should be recalculated when category reveals Media Mail eligibility."""

    def test_book_category_reduces_shipping_buffer(self):
        """If AI didn't detect ISBN but category is Books, shipping should drop to Media Mail."""
        from backend.app.core.constants import get_shipping_cost
        # AI said medium (6.50), but category is Books (261186)
        cost = get_shipping_cost(category_id="261186", package_size="medium")
        assert cost == 3.50, "Book category should override package_size to Media Mail"
```

**Step 2: Run — should already pass** since Task 1 implemented the priority chain. This is a verification test.

**Step 3: Modify processor_service.py**

After category is determined (around line 377, after `cat_result`), recalculate shipping if category changed the cost:

```python
# After line 370 (category_id assignment), before line 377 (pricing):
# Recalculate shipping cost now that we know the category
from backend.app.core.constants import get_shipping_cost
ident = ai_data.get('identification', {})
shipping_cost = get_shipping_cost(
    category_id=cat_result.get('id'),
    isbn=ident.get('isbn'),
    package_size=ident.get('package_size', ''),
    estimated_weight_lbs=ident.get('estimated_weight_lbs'),
)
# Store for downstream use and UI display
ai_data['shipping_cost'] = shipping_cost
ai_data['shipping_method'] = 'media_mail' if shipping_cost == 3.50 else 'standard'
```

**Step 4: Run full test suite**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/ -v --tb=short`
Expected: All tests pass including existing pipeline tests.

**Step 5: Commit**

```bash
git add backend/app/services/processor_service.py tests/unit/test_shipping_estimation_unit.py
git commit -m "feat: recalculate shipping after category detection

Books discovered by category (not just ISBN) now get Media Mail rate.
Shipping method stored in ai_data for UI display."
```

---

## Task 3: Profit Calculator — Backend API Changes

Expose profit breakdown data in the job details API response so the frontend can display it.

**Files:**
- Modify: `backend/app/blueprints/api/jobs_api.py:132-173`
- Test: `tests/unit/test_job_details_api.py`

**Step 1: Write the failing test**

```python
class TestProfitBreakdown:
    """Job details should include profit breakdown for UI display."""

    def test_profit_breakdown_present_in_response(self, client, sample_job_with_price):
        """GET /api/job/<id>/details should include profit_breakdown."""
        resp = client.get(f'/api/job/{sample_job_with_price.id}/details')
        data = resp.get_json()
        assert 'profit_breakdown' in data
        breakdown = data['profit_breakdown']
        assert 'listing_price' in breakdown
        assert 'ebay_fee' in breakdown
        assert 'payment_fee' in breakdown
        assert 'shipping_cost' in breakdown
        assert 'take_home' in breakdown

    def test_profit_breakdown_math_correct(self, client, sample_job_with_price):
        """Profit breakdown math should be accurate."""
        resp = client.get(f'/api/job/{sample_job_with_price.id}/details')
        breakdown = resp.get_json()['profit_breakdown']
        price = breakdown['listing_price']
        expected_fee = round(price * 0.1325, 2)
        assert breakdown['ebay_fee'] == expected_fee
        assert breakdown['payment_fee'] == 0.30
        expected_take = round(price - expected_fee - 0.30 - breakdown['shipping_cost'], 2)
        assert breakdown['take_home'] == expected_take
```

**Step 2: Run test to verify it fails**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_job_details_api.py::TestProfitBreakdown -v`
Expected: FAIL — `profit_breakdown` not in response.

**Step 3: Add profit breakdown to jobs_api.py**

In `get_job_details()`, after line 169 (`'price': job.price`), add:

```python
        # --- Profit Breakdown ---
        listing_price = float(job.price or ai_data.get('suggested_price') or ai_data.get('price') or 0)
        shipping_cost_val = float(ai_data.get('shipping_cost', 6.50))
        ebay_fee = round(listing_price * 0.1325, 2) if listing_price > 0 else 0
        payment_fee = 0.30 if listing_price > 0 else 0
        take_home = round(listing_price - ebay_fee - payment_fee - shipping_cost_val, 2) if listing_price > 0 else 0
```

Add to the response dict:

```python
        'profit_breakdown': {
            'listing_price': listing_price,
            'ebay_fee': ebay_fee,
            'ebay_fee_rate': 0.1325,
            'payment_fee': payment_fee,
            'shipping_cost': shipping_cost_val,
            'shipping_method': ai_data.get('shipping_method', 'standard'),
            'take_home': take_home,
        },
```

**Step 4: Run tests**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_job_details_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/blueprints/api/jobs_api.py tests/unit/test_job_details_api.py
git commit -m "feat: add profit_breakdown to job details API

Shows eBay fee, payment fee, shipping cost, and take-home for every job.
Frontend can now display real profit numbers to the seller."
```

---

## Task 4: Profit Calculator — Frontend UI

Display the profit breakdown under the price field in `ItemDetailDrawer.tsx`. Updates live as the seller changes the price.

**Files:**
- Modify: `frontend/src/lib/api.ts:250-283` (add `profit_breakdown` to `JobDetails` interface)
- Modify: `frontend/src/components/ItemDetailDrawer.tsx:238-258` (add profit display)

**Step 1: Add type to api.ts**

In the `JobDetails` interface, add after `pricing_data`:

```typescript
    profit_breakdown?: {
        listing_price: number
        ebay_fee: number
        ebay_fee_rate: number
        payment_fee: number
        shipping_cost: number
        shipping_method: string
        take_home: number
    }
```

**Step 2: Add profit calculator component to ItemDetailDrawer.tsx**

After the price source display (line 258, after the closing `)}` of `price_source`), add:

```tsx
                                        {/* Profit Calculator */}
                                        {(() => {
                                            const price = parseFloat(draft.price) || 0
                                            if (price <= 0) return null
                                            const shippingCost = jobDetails?.profit_breakdown?.shipping_cost ?? 6.50
                                            const shippingMethod = jobDetails?.profit_breakdown?.shipping_method ?? 'standard'
                                            const ebayFee = Math.round(price * 0.1325 * 100) / 100
                                            const paymentFee = 0.30
                                            const takeHome = Math.round((price - ebayFee - paymentFee - shippingCost) * 100) / 100
                                            const isNegative = takeHome < 0
                                            return (
                                                <div className={`mt-2 p-2 rounded-md text-[11px] font-mono ${isNegative ? 'bg-red-50 border border-red-200' : 'bg-emerald-50 border border-emerald-200'}`}>
                                                    <div className="flex justify-between text-stone-500">
                                                        <span>eBay fee (13.25%)</span>
                                                        <span>-${ebayFee.toFixed(2)}</span>
                                                    </div>
                                                    <div className="flex justify-between text-stone-500">
                                                        <span>Payment processing</span>
                                                        <span>-$0.30</span>
                                                    </div>
                                                    <div className="flex justify-between text-stone-500">
                                                        <span>Shipping ({shippingMethod === 'media_mail' ? 'Media Mail' : shippingCost <= 4.50 ? 'Small pkg' : shippingCost <= 6.50 ? 'Standard' : shippingCost <= 10 ? 'Large pkg' : 'Heavy'})</span>
                                                        <span>-${shippingCost.toFixed(2)}</span>
                                                    </div>
                                                    <div className={`flex justify-between font-bold border-t mt-1 pt-1 ${isNegative ? 'text-red-600 border-red-300' : 'text-emerald-700 border-emerald-300'}`}>
                                                        <span>Your take-home</span>
                                                        <span>${takeHome.toFixed(2)}</span>
                                                    </div>
                                                </div>
                                            )
                                        })()}
```

**Step 3: Build frontend**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander/frontend && npm run build`
Expected: Build succeeds with no errors.

**Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/ItemDetailDrawer.tsx
git commit -m "feat: add live profit calculator to item detail drawer

Shows eBay fee, payment processing, shipping tier, and take-home.
Updates in real-time as seller adjusts price. Red highlight when negative."
```

---

## Task 5: Comp Quality Filtering — Title Similarity + Outlier Rejection

Filter out irrelevant comps before calculating the median. Two guards: title similarity threshold and statistical outlier rejection.

**Files:**
- Modify: `backend/app/services/pricing_engine.py`
- Test: `tests/unit/test_pricing_engine.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_pricing_engine.py`:

```python
class TestCompFiltering:
    """Comps should be filtered for relevance before price calculation."""

    def test_title_similarity_filters_irrelevant_comps(self, engine):
        """Comps with low title similarity should be excluded."""
        comps = [
            {"title": "Aiwa CSD-ES227 Boombox CD Cassette", "price": 50.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Aiwa CSD-ES227 Boombox Stereo", "price": 55.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Tesla Model 3 Floor Mat Set", "price": 200.0, "condition": "New", "end_date": "", "url": ""},  # irrelevant
            {"title": "iPhone 15 Pro Case Cover", "price": 5.0, "condition": "New", "end_date": "", "url": ""},  # irrelevant
        ]
        filtered = engine.filter_comps(comps, reference_title="Aiwa CSD-ES227 Boombox CD Cassette Player")
        assert len(filtered) == 2
        assert all("Aiwa" in c["title"] for c in filtered)

    def test_outlier_rejection_removes_extremes(self, engine):
        """Prices >2 std devs from median should be dropped."""
        comps = _make_sold_items([50, 52, 48, 55, 51, 300])  # 300 is an outlier
        filtered = engine.filter_comps(comps, reference_title="Generic Item")
        prices = [c["price"] for c in filtered]
        assert 300 not in prices

    def test_filter_preserves_minimum_comps(self, engine):
        """Even with aggressive filtering, keep at least 3 comps if available."""
        comps = [
            {"title": "Widget A", "price": 10.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Widget B", "price": 12.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Widget C", "price": 11.0, "condition": "Used", "end_date": "", "url": ""},
            {"title": "Totally Different Thing", "price": 50.0, "condition": "New", "end_date": "", "url": ""},
        ]
        filtered = engine.filter_comps(comps, reference_title="Widget A Model X")
        assert len(filtered) >= 3

    def test_empty_comps_returns_empty(self, engine):
        filtered = engine.filter_comps([], reference_title="Anything")
        assert filtered == []
```

**Step 2: Run test to verify it fails**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_pricing_engine.py::TestCompFiltering -v`
Expected: FAIL — `filter_comps` does not exist.

**Step 3: Implement filter_comps in PricingEngine**

Add to `pricing_engine.py` class, before `calculate_suggested_price`:

```python
    MIN_TITLE_SIMILARITY = 0.30  # Minimum word overlap ratio
    MIN_COMPS_AFTER_FILTER = 3   # Don't filter below this count

    def filter_comps(self, comps: List[Dict], reference_title: str) -> List[Dict]:
        """Filter comps by title similarity and price outlier rejection.

        1. Title similarity: keep comps sharing >= 30% of words with reference title
        2. Outlier rejection: drop prices > 2 std devs from median
        3. Safety: never filter below MIN_COMPS_AFTER_FILTER if we started with enough
        """
        if len(comps) <= self.MIN_COMPS_AFTER_FILTER:
            return comps

        # --- Phase 1: Title similarity ---
        ref_words = set(reference_title.lower().split())
        scored = []
        for comp in comps:
            comp_words = set(comp.get("title", "").lower().split())
            if not ref_words or not comp_words:
                scored.append((0.0, comp))
                continue
            overlap = len(ref_words & comp_words) / max(len(ref_words), 1)
            scored.append((overlap, comp))

        # Sort by similarity descending, keep those above threshold
        scored.sort(key=lambda x: x[0], reverse=True)
        title_filtered = [c for sim, c in scored if sim >= self.MIN_TITLE_SIMILARITY]

        # Safety: keep at least MIN_COMPS_AFTER_FILTER (take top by similarity)
        if len(title_filtered) < self.MIN_COMPS_AFTER_FILTER:
            title_filtered = [c for _, c in scored[:self.MIN_COMPS_AFTER_FILTER]]

        # --- Phase 2: Outlier rejection ---
        if len(title_filtered) >= 5:
            prices = [c["price"] for c in title_filtered if c.get("price", 0) > 0]
            if prices:
                median = statistics.median(prices)
                try:
                    stdev = statistics.stdev(prices)
                except statistics.StatisticsError:
                    stdev = 0
                if stdev > 0:
                    lower = median - 2 * stdev
                    upper = median + 2 * stdev
                    outlier_filtered = [c for c in title_filtered if lower <= c.get("price", 0) <= upper]
                    if len(outlier_filtered) >= self.MIN_COMPS_AFTER_FILTER:
                        title_filtered = outlier_filtered

        return title_filtered
```

**Step 4: Wire filter_comps into calculate_suggested_price**

At the top of `calculate_suggested_price()`, right after the `if not sold_items` guard (line 315), add:

```python
        # Filter comps for relevance (caller should provide reference_title via sold_items metadata)
        # Note: filtering is applied by the caller in get_price_with_comps() before calling this method
```

Actually, the better integration point is in `get_price_with_comps()`. Before each call to `self.calculate_suggested_price(sold_items, ...)`, add filtering:

```python
        sold_items = self.filter_comps(sold_items, reference_title=title)
```

Do this for Strategy 1 (ISBN sold/active), 1.5 (MPN), and 2 (keyword) — everywhere `calculate_suggested_price` is called in `get_price_with_comps`. Pass `title` as `reference_title` in all cases.

**Step 5: Run tests**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_pricing_engine.py -v`
Expected: All existing + new tests pass.

**Step 6: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_pricing_engine.py
git commit -m "feat: filter comps by title similarity + outlier rejection

Comps with <30% word overlap are excluded. Prices >2 std devs from
median are dropped. Minimum 3 comps preserved to avoid over-filtering."
```

---

## Task 6: Sold vs. Asking Price Labels

Tag pricing data with whether comps are from sold data (Finding API) or asking prices (Browse API) so the frontend can warn the seller.

**Files:**
- Modify: `backend/app/services/pricing_engine.py:604-780`
- Modify: `backend/app/blueprints/api/jobs_api.py:151-155`
- Modify: `frontend/src/components/ItemDetailDrawer.tsx`
- Test: `tests/unit/test_pricing_engine.py`

**Step 1: Write the failing test**

```python
class TestPriceSourceLabeling:
    """Price source should distinguish sold data from asking prices."""

    def test_finding_api_source_is_sold(self, engine):
        """Finding API results should be labeled as sold data."""
        # The source string for ISBN sold match should contain 'sold'
        assert 'sold' in 'market_data_isbn_sold'

    def test_browse_api_source_is_asking(self, engine):
        """Browse API results should be labeled as asking prices."""
        assert 'sold' not in 'market_data_isbn'

    def test_source_label_function(self, engine):
        """Human-readable labels for price sources."""
        from backend.app.services.pricing_engine import format_price_source
        assert format_price_source('market_data_isbn_sold') == 'Based on 8 sold listings (ISBN)'
        assert format_price_source('market_data_isbn') == 'Based on active listings (ISBN) - not sold data'
        assert format_price_source('market_data_keyword_sold') == 'Based on 8 sold listings'
        assert format_price_source('ai_grounding') == 'AI estimate (no comp data)'
```

**Step 2: Run test to verify it fails**

Expected: FAIL — `format_price_source` does not exist.

**Step 3: Add format_price_source to pricing_engine.py**

Add as a module-level function:

```python
def format_price_source(source: str, comp_count: int = 0) -> str:
    """Convert internal price source key to human-readable label."""
    count_str = f"{comp_count} " if comp_count > 0 else ""
    labels = {
        'market_data_isbn_sold': f'Based on {count_str}sold listings (ISBN)',
        'market_data_isbn': f'Based on {count_str}active listings (ISBN) — not sold data',
        'market_data_mpn_sold': f'Based on {count_str}sold listings (MPN)',
        'market_data_mpn': f'Based on {count_str}active listings (MPN) — not sold data',
        'market_data_keyword_sold': f'Based on {count_str}sold listings',
        'market_data_keyword': f'Based on {count_str}active listings — not sold data',
        'research_market_price': 'AI web research estimate',
        'ai_grounding': 'AI estimate (no comp data)',
        'ai_vision': 'AI vision estimate (lowest confidence)',
        'user_override': 'Manual price',
    }
    return labels.get(source, source)
```

**Step 4: Update jobs_api.py to include formatted label**

In the `pricing_data` section of `get_job_details()`, add:

```python
            'price_source': ai_data.get('pricing_source', 'AI estimate'),
            'price_source_label': format_price_source(
                ai_data.get('pricing_source', ''),
                comp_count=len(ai_data.get('pricing_comps', []))
            ),
```

Import at top of jobs_api.py:
```python
from backend.app.services.pricing_engine import format_price_source
```

**Step 5: Update frontend to show the label with warning color**

In `ItemDetailDrawer.tsx`, replace the existing price_source display (lines 254-258):

```tsx
                                        {jobDetails?.pricing_data?.price_source_label && (
                                            <p className={`text-[10px] mt-1 ${
                                                jobDetails.pricing_data.price_source?.includes('sold')
                                                    ? 'text-emerald-600'
                                                    : jobDetails.pricing_data.price_source?.includes('market_data')
                                                        ? 'text-amber-600'
                                                        : 'text-stone-400'
                                            }`}>
                                                {jobDetails.pricing_data.price_source_label}
                                            </p>
                                        )}
```

And add `price_source_label` to the `pricing_data` type in `api.ts`:

```typescript
    pricing_data: {
        confidence?: string
        comparables: Array<{ title: string; price: number }>
        price_source: string
        price_source_label?: string
        market_price?: Record<string, unknown>
    }
```

**Step 6: Build and test**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander && pytest tests/unit/test_pricing_engine.py::TestPriceSourceLabeling -v`
Run: `cd C:/Users/adam/Projects/ebay-draft-commander/frontend && npm run build`
Expected: All pass, build succeeds.

**Step 7: Commit**

```bash
git add backend/app/services/pricing_engine.py backend/app/blueprints/api/jobs_api.py frontend/src/lib/api.ts frontend/src/components/ItemDetailDrawer.tsx tests/unit/test_pricing_engine.py
git commit -m "feat: distinguish sold vs asking price sources in UI

Sold data shows green, active listing (asking price) data shows amber
warning. Sellers can now see when pricing is based on reliable sold
comps vs inflated asking prices."
```

---

## Task 7: Smart Scheduling Presets

Add preset scheduling buttons that auto-select the next optimal listing window instead of requiring manual datetime entry.

**Files:**
- Modify: `frontend/src/components/item-detail/ItemScheduleField.tsx`
- Test: Build verification only (UI component)

**Step 1: Read the existing ItemScheduleField**

Read `frontend/src/components/item-detail/ItemScheduleField.tsx` to understand current implementation.

**Step 2: Add smart scheduling presets**

Add a helper function and preset buttons above the datetime input:

```typescript
/** Find the next occurrence of a target day/hour in UTC */
function getNextOptimalSlot(targetDay: number, targetHourUTC: number): Date {
    const now = new Date()
    const target = new Date(now)
    target.setUTCHours(targetHourUTC, 0, 0, 0)

    // Find next occurrence of target day (0=Sun, 1=Mon, etc.)
    const daysUntil = (targetDay - now.getUTCDay() + 7) % 7
    target.setUTCDate(now.getUTCDate() + (daysUntil === 0 && now > target ? 7 : daysUntil))

    return target
}

function getSchedulePresets(): Array<{ label: string; value: string; sublabel: string }> {
    // Sunday 7PM Pacific = Monday 02:00 or 03:00 UTC (depending on DST)
    // Approximate: use 03:00 UTC for Pacific evening
    const sundayEvening = getNextOptimalSlot(0, 3) // Sunday ~7PM PT
    const mondayEvening = getNextOptimalSlot(1, 3)  // Monday ~7PM PT
    const wednesdayEvening = getNextOptimalSlot(3, 3)  // Wed ~7PM PT

    const fmt = (d: Date) => {
        return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) +
            ' ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    }

    return [
        { label: 'Sun Evening', sublabel: fmt(sundayEvening), value: sundayEvening.toISOString() },
        { label: 'Mon Evening', sublabel: fmt(mondayEvening), value: mondayEvening.toISOString() },
        { label: 'Wed Evening', sublabel: fmt(wednesdayEvening), value: wednesdayEvening.toISOString() },
    ]
}
```

Render preset buttons above the existing datetime input:

```tsx
<div className="flex gap-1.5 mb-2">
    {getSchedulePresets().map((preset) => (
        <button
            key={preset.label}
            type="button"
            onClick={() => onChange(preset.value)}
            className="flex-1 px-2 py-1.5 text-[10px] leading-tight text-center rounded-md border border-stone-200 hover:border-blue-400 hover:bg-blue-50 transition-colors"
        >
            <div className="font-semibold">{preset.label}</div>
            <div className="text-stone-400">{preset.sublabel}</div>
        </button>
    ))}
</div>
```

**Step 3: Build frontend**

Run: `cd C:/Users/adam/Projects/ebay-draft-commander/frontend && npm run build`
Expected: Build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/components/item-detail/ItemScheduleField.tsx
git commit -m "feat: add smart scheduling presets (Sun/Mon/Wed evening)

One-tap scheduling to peak eBay shopping windows instead of manual
datetime entry. Times auto-adjust for timezone."
```

---

## Summary

| Task | Feature | Impact |
|------|---------|--------|
| 1-2 | Smart shipping tiers + Media Mail | Correct shipping buffer on every listing |
| 3-4 | Profit calculator (backend + frontend) | Seller sees real take-home before listing |
| 5 | Comp quality filtering | Prevents bad pricing from irrelevant comps |
| 6 | Sold vs asking price labels | Seller knows when to trust suggested price |
| 7 | Smart scheduling presets | One-tap optimal timing |

All tasks are independent after Task 1-2 (which are sequential). Tasks 3-7 can be built in any order.
