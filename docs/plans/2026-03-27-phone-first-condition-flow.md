# Phone-First Condition Flow + Smart Pricing

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users snap photos on their phone, have AI process everything in the background, then pick condition from valid-only options — with pricing driven by real same-condition comp data instead of static multipliers.

**Architecture:** Split the existing single-pass pipeline (`processor_service.py:create_listing()`) into two phases. Phase 1 (AI + comps) runs automatically after upload. Phase 2 (condition pricing + eBay submission) runs after user picks condition. A new `awaiting_condition` job status bridges the two phases. The frontend replaces the dead `QuickListingForm` with a condition review screen.

**Tech Stack:** Flask + SQLAlchemy (backend), React 18 + Zustand + Tailwind (frontend), Socket.IO (real-time), eBay Taxonomy/Finding APIs

---

## Codebase Context (READ THIS FIRST)

### Key File Locations
```
backend/
  app/
    services/
      queue_job.py          # JobStatus enum (line 18), QueueJob dataclass (line 32)
      queue_manager.py       # _process_job() at line 807, update_job() at line 275
      processor_service.py   # create_listing() at line 260 — THE MAIN PIPELINE
      listing_ai_agent.py    # analyze_item() at line 55, get_final_pricing() at line 131
      pricing_engine.py      # CONDITION_MULTIPLIERS at line 51, calculate_suggested_price() at ~line 297
      ebay/taxonomy.py       # get_valid_condition_ids() at line 306, validate_condition_for_category() at line 344
    core/
      constants.py           # CONDITION_MAP (line 7), CONDITION_ID_MAP (line 27), CONDITION_ENUM_TO_DISPLAY (line 45)
    blueprints/api/
      jobs_api.py            # Job CRUD endpoints
      lookup_api.py          # Book lookup XSS at line 44
  config.py                  # Silent .env failure at line 40

frontend/src/
  App.tsx                    # Tab routing, imports QuickListingForm (line 10), PhotoEditor (line 11)
  lib/api.ts                 # JobStatus type (line 4), apiFetch wrapper (line 49)
  store/useCommanderStore.ts # Zustand store, CommanderState interface (line 6)
  components/
    QuickListingForm.tsx     # DEAD — to be replaced
    PhotoEditor.tsx          # DEAD — to be deleted
    MobileNavBar.tsx         # Bottom nav tabs (line 6: tab definitions)
    Sidebar.tsx              # Desktop nav (line 9: navGroups)
    MobileUploadFAB.tsx      # Phone upload button (working, keep as-is)
```

### Current Pipeline Flow (processor_service.py:260-509)
```
create_listing(job_obj):
  1. _determine_condition()        → user > metadata > folder > DEFAULT_CONDITION
  2. Collect images from folder
  3. ai_agent.analyze_item()       → Gemini vision + research (cached in ai_data)
  3b. _refine_condition_from_ai()  → AI can override DEFAULT_CONDITION
  4. Category mapping + aspect enrichment
  5. ai_agent.get_final_pricing()  → Finding API comps + static condition multiplier
  6. Image upload to eBay EPS
  7. Template rendering
  8. Auto-publish guard (confidence, price, missing aspects)
  9. Trading API AddFixedPriceItem
```

### Current Job Status Handling (queue_manager.py:842-872)
```python
# In _process_job(), after create_listing() returns:
if result.get('status') == 'pending_review':
    job.status = JobStatus.PENDING_REVIEW
elif result.get('success') or result.get('listing_id'):
    job.status = JobStatus.COMPLETED
else:
    job.status = JobStatus.FAILED
```
**Key insight:** Adding `awaiting_condition` status handling follows the exact same pattern as `pending_review`.

### Current Condition Multipliers (pricing_engine.py:51-61)
```python
CONDITION_MULTIPLIERS = {
    "New": 1.0,
    "New - Open Box": 0.90,
    "Used - Like New": 0.85,
    "Used - Good": 0.75,
    "Used - Acceptable": 0.60,
    "For Parts": 0.40,
    "For Parts or Not Working": 0.40,
    "New Old Stock": 0.95,
    "New other (see details)": 0.90,
}
```
**Problem:** A flat 0.75 for "Used - Good" is wrong — a vintage book holds 90%+ value while electronics might be 50%. We replace this with comp-based pricing.

### eBay Condition ID ↔ Display Mappings (constants.py)
```python
CONDITION_ID_MAP = {
    'NEW': '1000', 'NEW_OTHER': '1500', 'LIKE_NEW': '3000',
    'USED_EXCELLENT': '3000', 'USED_VERY_GOOD': '4000',
    'USED_GOOD': '5000', 'USED_ACCEPTABLE': '6000',
    'FOR_PARTS_OR_NOT_WORKING': '7000'
}
# Reverse: id → label needed for frontend condition picker
```

### Frontend Tab System
- `App.tsx` line 30: `TAB_ORDER = ['dashboard', 'review', 'inventory', 'analytics', 'settings']`
- `App.tsx` line 136: `{activeTab === 'create' && <QuickListingForm />}` (dead tab, not in TAB_ORDER)
- `Sidebar.tsx` line 9: `navGroups` array defines desktop sidebar items
- `MobileNavBar.tsx` line 6: `tabs` array defines mobile bottom nav items
- Neither sidebar nor mobile nav includes a "condition review" tab yet

### Frontend API Pattern (api.ts)
```typescript
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init)
    if (!res.ok) { throw new Error(...) }
    return res.json()
}
// All API functions follow this pattern: export async function name(): Promise<Type>
```

### Existing Valid Conditions Infrastructure (taxonomy.py:306-341)
```python
def get_valid_condition_ids(category_id: str) -> list:
    """Fetch valid condition IDs for a category via eBay Sell Metadata API.
    Returns list like ['1000', '1500', '3000', '7000']. Cached."""
```
Already exists and works. Just needs an HTTP endpoint to expose it to frontend.

---

## Task 1: Add `AWAITING_CONDITION` Job Status

**Files:**
- Modify: `backend/app/services/queue_job.py:18-28` (add enum value)
- Modify: `frontend/src/lib/api.ts:4` (add to JobStatus union type)

**What to do:**

Add `AWAITING_CONDITION = "awaiting_condition"` to `JobStatus` enum in `queue_job.py` after `PROCESSING`:

```python
class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_CONDITION = "awaiting_condition"  # AI done, waiting for user condition
    COMPLETED = "completed"
    # ... rest unchanged
```

Update frontend `api.ts` line 4:
```typescript
export type JobStatus = 'pending' | 'processing' | 'awaiting_condition' | 'completed' | 'failed' | 'paused' | 'skipped' | 'scheduled' | 'needs_review' | 'pending_review'
```

**Commit:** `feat: add AWAITING_CONDITION job status`

---

## Task 2: Add Valid Conditions API Endpoint

**Files:**
- Modify: `backend/app/blueprints/api/lookup_api.py` (add route after line 59)
- Test: `tests/unit/test_valid_conditions_api.py` (new)

**Step 1: Write test**

```python
"""Tests for GET /api/lookup/category/<id>/conditions"""
import pytest
from unittest.mock import patch


class TestValidConditionsEndpoint:
    @patch('backend.app.blueprints.api.lookup_api.get_valid_condition_ids')
    def test_returns_valid_conditions(self, mock_get_ids, client):
        mock_get_ids.return_value = ['1000', '1500', '3000', '5000']
        resp = client.get('/api/lookup/category/175673/conditions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['category_id'] == '175673'
        assert len(data['conditions']) == 4
        assert all('id' in c and 'label' in c for c in data['conditions'])

    @patch('backend.app.blueprints.api.lookup_api.get_valid_condition_ids')
    def test_unknown_category_returns_empty(self, mock_get_ids, client):
        mock_get_ids.return_value = []
        resp = client.get('/api/lookup/category/999999/conditions')
        assert resp.status_code == 200
        assert resp.get_json()['condition_ids'] == []
```

**Step 2: Implement endpoint**

Add to `lookup_api.py` (after the existing `/lookup/category/<id>/aspects` route):

```python
@lookup_bp.route('/lookup/category/<category_id>/conditions', methods=['GET'])
def get_valid_conditions(category_id):
    """Return valid eBay condition IDs and labels for a category."""
    from backend.app.services.ebay.taxonomy import get_valid_condition_ids
    from backend.app.core.constants import CONDITION_ID_MAP

    valid_ids = get_valid_condition_ids(category_id)
    # Build reverse map: condition_id -> display label
    id_to_label = {}
    for enum_key, cid in CONDITION_ID_MAP.items():
        display = enum_key.replace('_', ' ').title()
        id_to_label.setdefault(str(cid), display)

    conditions = [{'id': cid, 'label': id_to_label.get(cid, f'Condition {cid}')} for cid in valid_ids]
    return jsonify({'category_id': category_id, 'condition_ids': valid_ids, 'conditions': conditions})
```

**Run:** `pytest tests/unit/test_valid_conditions_api.py -v`
**Commit:** `feat: add GET /api/lookup/category/<id>/conditions endpoint`

---

## Task 3: Split Pipeline — Phase 1 Stops at `awaiting_condition`

**Files:**
- Modify: `backend/app/services/processor_service.py` (in `create_listing()`, between step 4c and step 5)
- Modify: `backend/app/services/queue_manager.py:842-872` (handle new status in `_process_job()`)
- Test: `tests/unit/test_pipeline_split.py` (new)

**The Split:** After AI analysis + category mapping + aspect enrichment (line ~358), but BEFORE pricing (line 360), check if condition is still the DEFAULT. If so, return `awaiting_condition`.

**Step 1: Write test**

```python
"""Tests for two-phase pipeline split."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestPipelineSplit:
    @patch('backend.app.services.processor_service.get_correction_cache')
    @patch('backend.app.services.processor_service.ProcessorService._validate_and_enrich_specifics')
    @patch('backend.app.services.listing_ai_agent.ListingAIAgent.analyze_item')
    def test_no_condition_returns_awaiting(self, mock_analyze, mock_enrich, mock_cache):
        """Job with no user_condition and no folder/metadata condition pauses."""
        from backend.app.services.processor_service import ProcessorService

        mock_analyze.return_value = {
            'success': True, 'ai_data': {'listing': {'suggested_title': 'Test'}, 'identification': {}},
            'title': 'Test Item', 'raw_description': 'Desc', 'item_specifics': {},
            'ai_suggested_price': 25.0, 'shipping_cost': 6.50,
            'category_id': '175673', 'confidence_score': 0.9
        }
        mock_enrich.return_value = []
        mock_cache.return_value.lookup.return_value = None

        job = MagicMock()
        job.folder_path = '/tmp/test_images'
        job.user_condition = None
        job.user_title = None
        job.user_price = None
        job.user_description = None
        job.job_metadata = {}
        job.ai_data = {}
        job.scheduled_time = None
        job.confidence_score = 0

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]):
            processor = ProcessorService()
            result = processor.create_listing(job)

        assert result['status'] == 'awaiting_condition'
        assert result['success'] is True
        assert 'category_id' in result
```

**Step 2: Modify `processor_service.py`**

Two changes needed:

**Change A:** In `_determine_condition()` (line 58-79), return `None` instead of `DEFAULT_CONDITION` when no source provides a condition:

```python
def _determine_condition(self, folder_path, metadata_condition, user_condition, log_callback=None):
    # ... existing user/metadata/folder checks unchanged ...

    # No condition from any source — return None to trigger awaiting_condition
    _log("Condition: None (will await user input)")
    return None
```

**Change B:** In `create_listing()`, after step 4c (line ~358) and before step 5 (line 360), insert the gate:

```python
        # --- PHASE 1 GATE: Pause if no condition determined ---
        if condition is None:
            _log("No condition determined — pausing for user input", level='warning')
            ai_data = job_obj.ai_data or {}
            ai_data['category_id'] = cat_result.get('id')
            ai_data['category_name'] = cat_result.get('name')
            if ebay_aspect_schema:
                ai_data['ebay_aspect_schema'] = ebay_aspect_schema
                ai_data.pop('ebay_required_aspects', None)
            job_obj.ai_data = ai_data

            result.update({
                "success": True,
                "status": "awaiting_condition",
                "title": analysis['title'],
                "category_id": cat_result.get('id'),
                "category_name": cat_result.get('name', ''),
                "confidence_score": confidence_score,
                "timing": {**result["timing"], "total": time.time() - start_time}
            })
            return result
```

**Change C:** In `queue_manager.py` `_process_job()` (line ~842), add handler for the new status. Insert before the `elif result.get('success')` check:

```python
                if result.get('status') == 'awaiting_condition':
                    job.status = JobStatus.AWAITING_CONDITION
                    job.title = result.get('title')
                    job.confidence_score = result.get('confidence_score')
                    job.timing = result.get('timing', {'total': elapsed})
                elif result.get('status') == 'pending_review':
                    # ... existing code unchanged
```

**Run:** `pytest tests/unit/test_pipeline_split.py -v` then `pytest tests/unit/ -v --tb=short`
**Commit:** `feat: split pipeline - phase 1 pauses at awaiting_condition when no condition`

---

## Task 4: Resume Pipeline Endpoint

**Files:**
- Modify: `backend/app/blueprints/api/jobs_api.py` (add 2 routes)
- Modify: `backend/app/services/queue_manager.py` (add `resume_with_condition()`)
- Test: `tests/unit/test_resume_pipeline.py` (new)

**Step 1: Write test**

```python
"""Tests for POST /api/job/<id>/set-condition"""
import pytest
from unittest.mock import patch, MagicMock


class TestResumeWithCondition:
    @patch('backend.app.blueprints.api.jobs_api.current_app')
    def test_set_condition_and_resume(self, mock_app, client):
        mock_qm = MagicMock()
        mock_qm.resume_with_condition.return_value = {'success': True, 'status': 'pending'}
        mock_app.config.get.return_value = mock_qm

        resp = client.post('/api/job/abc123/set-condition', json={'condition': 'USED_GOOD'})
        assert resp.status_code == 200
        mock_qm.resume_with_condition.assert_called_once_with('abc123', 'USED_GOOD')

    def test_missing_condition_returns_400(self, client):
        resp = client.post('/api/job/abc123/set-condition', json={})
        assert resp.status_code == 400

    @patch('backend.app.blueprints.api.jobs_api.current_app')
    def test_batch_set_condition(self, mock_app, client):
        mock_qm = MagicMock()
        mock_qm.resume_with_condition.return_value = {'success': True}
        mock_app.config.get.return_value = mock_qm

        resp = client.post('/api/jobs/batch-set-condition', json={
            'items': [
                {'job_id': 'abc', 'condition': 'USED_GOOD'},
                {'job_id': 'def', 'condition': 'NEW'},
            ]
        })
        assert resp.status_code == 200
        assert mock_qm.resume_with_condition.call_count == 2
```

**Step 2: Add endpoints to `jobs_api.py`**

```python
@jobs_bp.route('/job/<job_id>/set-condition', methods=['POST'])
def set_condition(job_id):
    """Set condition on an awaiting_condition job and resume pipeline."""
    data = request.get_json() or {}
    condition = data.get('condition')
    if not condition:
        return error_response('condition is required', 400)
    qm = current_app.config.get('queue_manager')
    result = qm.resume_with_condition(job_id, condition)
    if not result.get('success'):
        return error_response(result.get('error', 'Resume failed'), 400)
    return jsonify(result)

@jobs_bp.route('/jobs/batch-set-condition', methods=['POST'])
def batch_set_condition():
    """Batch set conditions and resume multiple jobs."""
    data = request.get_json() or {}
    items = data.get('items', [])
    if not items:
        return error_response('items array is required', 400)
    qm = current_app.config.get('queue_manager')
    results = []
    for item in items:
        job_id, condition = item.get('job_id'), item.get('condition')
        if job_id and condition:
            results.append({'job_id': job_id, **qm.resume_with_condition(job_id, condition)})
    return jsonify({'results': results})
```

**Step 3: Add `resume_with_condition()` to `queue_manager.py`**

```python
def resume_with_condition(self, job_id: str, condition: str) -> dict:
    """Set user_condition and re-queue an awaiting_condition job."""
    session = self.SessionFactory()
    try:
        db_job = session.query(self.JobModel).filter_by(id=job_id).first()
        if not db_job:
            return {'success': False, 'error': 'Job not found'}
        if db_job.status != JobStatus.AWAITING_CONDITION.value:
            return {'success': False, 'error': f'Job is {db_job.status}, not awaiting_condition'}

        db_job.user_condition = condition
        db_job.status = JobStatus.PENDING.value
        session.commit()

        job = self._db_to_queue_job(db_job)
        self.emit_event('job_update', job.to_dict())

        if not self.is_processing():
            self.start_processing()

        return {'success': True, 'status': 'pending'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()
```

**Run:** `pytest tests/unit/test_resume_pipeline.py -v`
**Commit:** `feat: add set-condition endpoint to resume awaiting_condition jobs`

---

## Task 5: Condition-Aware Comp Pricing

**Files:**
- Modify: `backend/app/services/pricing_engine.py` (replace lines ~346-384 in `calculate_suggested_price()`)
- Test: `tests/unit/test_condition_comp_pricing.py` (new)

**The Change:** Instead of applying a static multiplier, filter comps to same-condition items first. Fall back to relative multiplier, then static.

**Step 1: Write test**

```python
"""Tests for condition-aware comp pricing."""
import pytest
from unittest.mock import patch


class TestConditionCompPricing:
    def _comp(self, price, condition):
        return {'price': price, 'condition': condition, 'title': 'Test'}

    def test_same_condition_comps_used_directly(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()
        comps = [
            self._comp(20.0, 'Used - Good'), self._comp(25.0, 'Used - Good'),
            self._comp(30.0, 'Used - Good'), self._comp(50.0, 'New'),
        ]
        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )
        # Median of same-condition = 25.0, not dragged up by the New comp
        assert 24.0 <= result['suggested_price'] <= 26.0
        assert result.get('pricing_method') == 'same_condition_comps'

    def test_few_same_condition_uses_relative(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()
        comps = [
            self._comp(20.0, 'Used - Good'),  # Only 1 match
            self._comp(50.0, 'New'), self._comp(48.0, 'New'),
        ]
        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )
        assert result.get('pricing_method') in ('relative_multiplier', 'static_multiplier')

    def test_no_condition_data_uses_static(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()
        comps = [{'price': 30.0, 'title': 'Test'}, {'price': 35.0, 'title': 'Test'}]
        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )
        assert result.get('pricing_method') == 'static_multiplier'
```

**Step 2: Replace multiplier logic in `calculate_suggested_price()`**

In `pricing_engine.py`, replace lines ~346-384 (the condition multiplier section) with:

```python
        # --- Condition-Aware Pricing (3-tier cascade) ---
        MIN_SAME_CONDITION_COMPS = 3

        from backend.app.core.constants import CONDITION_ENUM_TO_DISPLAY
        cond_key = our_condition
        if cond_key in CONDITION_ENUM_TO_DISPLAY:
            cond_key = CONDITION_ENUM_TO_DISPLAY[cond_key]
        if "new old stock" in cond_key.lower() or "nos" in cond_key.lower():
            cond_key = "New Old Stock"

        our_multiplier = self.CONDITION_MULTIPLIERS.get(cond_key, 0.75)

        # Tier 1: Filter comps to same condition
        same_cond_prices = []
        for item in sold_items:
            comp_mult = self._resolve_condition_multiplier(item.get("condition", ""))
            if comp_mult is not None and abs(comp_mult - our_multiplier) < 0.05:
                same_cond_prices.append(item['price'])

        if len(same_cond_prices) >= MIN_SAME_CONDITION_COMPS:
            base_price = statistics.median(same_cond_prices)
            multiplier = 1.0
            pricing_method = 'same_condition_comps'
            reasoning_prefix = f"Median of {len(same_cond_prices)} same-condition comps"
        else:
            # Tier 2: Relative multiplier from all comps
            comp_multipliers = []
            for item in sold_items:
                cm = self._resolve_condition_multiplier(item.get("condition", ""))
                if cm is not None:
                    comp_multipliers.append(cm)

            if comp_multipliers:
                avg_comp = statistics.mean(comp_multipliers)
                multiplier = our_multiplier / avg_comp if avg_comp > 0 else our_multiplier
                multiplier = max(0.40, min(1.30, multiplier))
                pricing_method = 'relative_multiplier'
                reasoning_prefix = f"{reasoning_prefix} (relative adj {multiplier:.2f}x)"
            else:
                # Tier 3: No condition data — static fallback
                multiplier = our_multiplier
                pricing_method = 'static_multiplier'
                reasoning_prefix = f"{reasoning_prefix} (static {cond_key} {multiplier}x)"

        suggested_price = round(base_price * multiplier, 2)
```

Add `'pricing_method': pricing_method` to the return dict (around line ~430).

**Run:** `pytest tests/unit/test_condition_comp_pricing.py tests/unit/test_pricing_engine.py tests/unit/test_research_pricing.py -v`
**Commit:** `feat: condition-aware comp pricing replaces static multipliers`

---

## Task 6: Frontend — Condition Review Screen

**Files:**
- Create: `frontend/src/components/ConditionReview.tsx`
- Modify: `frontend/src/lib/api.ts` (add 3 functions)
- Modify: `frontend/src/App.tsx` (swap QuickListingForm → ConditionReview, remove PhotoEditor)
- Modify: `frontend/src/components/Sidebar.tsx` (add condition review tab with badge)
- Modify: `frontend/src/components/MobileNavBar.tsx` (add condition review tab with badge)
- Delete: `frontend/src/components/PhotoEditor.tsx`
- Delete: `frontend/src/components/QuickListingForm.tsx`

**Step 1: Add API functions to `api.ts`**

Add after the existing exports (after line ~160):

```typescript
export interface ConditionOption {
    id: string
    label: string
}

export async function fetchValidConditions(categoryId: string): Promise<ConditionOption[]> {
    const data = await apiFetch<{ conditions: ConditionOption[] }>(
        `${API_BASE}/lookup/category/${categoryId}/conditions`
    )
    return data.conditions
}

export async function setJobCondition(jobId: string, condition: string): Promise<{ success: boolean }> {
    return apiFetch(`${API_BASE}/job/${jobId}/set-condition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ condition })
    })
}

export async function batchSetCondition(
    items: Array<{ job_id: string; condition: string }>
): Promise<{ results: Array<{ job_id: string; success: boolean }> }> {
    return apiFetch(`${API_BASE}/jobs/batch-set-condition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
    })
}
```

**Step 2: Create `ConditionReview.tsx`**

Mobile-first card UI. Each card shows:
- Job thumbnail (via `/api/job/{id}/image/{thumbnail_name}`)
- AI title
- Category name badge
- `<Select>` with only valid conditions for that category (fetched from Task 2 endpoint)
- Submit button per card + "Submit All" batch button

Key patterns to follow:
- Use `useCommanderStore` to get `jobs` and filter by `status === 'awaiting_condition'`
- Cache condition options by `category_id` (many items share categories)
- After submit, toast success and jobs auto-update via Socket.IO `job_update` event
- Empty state: "All caught up! No items waiting for condition."
- Use existing shadcn `Select`, `Card`, `Button` from `@/components/ui/`

**Step 3: Update `App.tsx`**

- Remove lines 10-11 (QuickListingForm, PhotoEditor imports)
- Add: `import { ConditionReview } from '@/components/ConditionReview'`
- Replace line 136 (`activeTab === 'create'`) with `activeTab === 'condition-review'`
- Remove lines 144-151 (photo-editor tab block)

**Step 4: Update `Sidebar.tsx` and `MobileNavBar.tsx`**

Add a "Condition" tab to both navigation components. Use `ClipboardCheck` or `CheckCircle` from lucide-react. Show badge count of `awaiting_condition` jobs.

In `Sidebar.tsx` navGroups (line 9), add to Workspace items:
```typescript
{ id: 'condition-review', icon: ClipboardCheck, label: 'Condition' },
```

In `MobileNavBar.tsx` tabs (line 6), add:
```typescript
{ id: 'condition-review', label: 'Condition', icon: ClipboardCheck },
```

**Step 5: Delete dead components**

```bash
git rm frontend/src/components/PhotoEditor.tsx frontend/src/components/QuickListingForm.tsx
```

**Step 6: Build and verify**

```bash
cd frontend && npm run build
```

**Commit:** `feat: condition review screen replaces dead QuickListingForm + PhotoEditor`

---

## Task 7: Fix XSS in Book Lookup

**Files:**
- Modify: `backend/app/blueprints/api/lookup_api.py:44`

**The fix:** Add `import html` at top, wrap all interpolated values in `html.escape()`:

```python
"description": f"<h2>{html.escape(title)}</h2><p><b>Author:</b> {html.escape(authors)}<br><b>Publisher:</b> {html.escape(str(book_data.get('publisher', '')))}<br><b>Year:</b> {html.escape(str(book_data.get('publishedDate', '')))}</p><p>{html.escape(str(book_data.get('description', '')))}</p>",
```

**Commit:** `fix: escape HTML in book lookup response to prevent XSS`

---

## Task 8: Fix Silent .env Failure

**Files:**
- Modify: `backend/config.py:40-41`

Replace:
```python
    except Exception:
        pass
```
With:
```python
    except FileNotFoundError:
        pass  # No .env file — rely on environment variables
    except Exception as e:
        import sys
        print(f"WARNING: Failed to load .env: {e}", file=sys.stderr)
```

**Commit:** `fix: log warning on .env load failure instead of silent pass`

---

## Task 9: Fix Integration Tests

**Files:**
- Modify: `tests/integration/test_full_pipeline.py` (~line 142)
- Modify: `tests/integration/test_smart_pricing.py`

The 3 full pipeline tests will fail because `create_listing()` now returns `awaiting_condition` when no condition is explicitly set.

**Fix:** Add `job.user_condition = 'USED_GOOD'` to the test's `_run_pipeline()` method after creating the job object (around line 142).

For `test_condition_multiplier_nos`, the assertion `0.95 != 0.9` needs updating to match the new pricing logic (same-condition comp filtering may change the result). Check what the new pricing returns and adjust the assertion.

**Run:** `pytest tests/integration/ -v`
**Commit:** `fix: update integration tests for two-phase pipeline`

---

## Task 10: Git Cleanup

**Files to delete:** `backup_claude.md`, `master_claude.md`, `nul`
**Files to gitignore:** `data/*.corrupt.*`, `data/*_dump.sql`, `data/*_recover.sql`

```bash
rm -f backup_claude.md master_claude.md nul
rm -f data/commander.db.corrupt.* data/commander_dump.sql data/commander_recover.sql
# Add to .gitignore: data/*.corrupt.*, data/*_dump.sql, data/*_recover.sql, nul
cd frontend && npm run build && cd ..
git add -A static/app/ .gitignore
```

**Commit:** `chore: clean stale files, update .gitignore, rebuild frontend`

---

## Dependency Graph

```
Task 1 (status enum) ──→ Task 3 (pipeline split) ──→ Task 4 (resume endpoint) ──→ Task 9 (fix tests)
Task 2 (conditions API) ──→ Task 6 (frontend)
Task 5 (comp pricing) — independent
Task 7 (XSS fix) — independent
Task 8 (.env fix) — independent
Task 10 (cleanup) — last
```

**Parallel-safe groups:**
- Group A: Tasks 1, 2, 5, 7, 8 (all independent)
- Group B: Task 3 (needs 1), Task 4 (needs 3)
- Group C: Task 6 (needs 1, 2, 4)
- Group D: Tasks 9, 10 (after everything else)
