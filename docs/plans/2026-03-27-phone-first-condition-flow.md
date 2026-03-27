# Phone-First Condition Flow + Smart Pricing

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users snap photos on their phone, have AI process everything in the background, then pick condition from valid-only options — with pricing driven by real same-condition comp data instead of static multipliers.

**Architecture:** Split the existing single-pass pipeline into two phases. Phase 1 (AI + comps) runs automatically after upload. Phase 2 (condition pricing + eBay submission) runs after user picks condition. A new `awaiting_condition` job status bridges the two phases. The frontend replaces the dead `QuickListingForm` with a swipeable condition review screen.

**Tech Stack:** Flask + SQLAlchemy (backend), React + Zustand + Tailwind (frontend), Socket.IO (real-time), eBay Taxonomy API (valid conditions), eBay Finding API (comps)

---

## Task 1: Add `AWAITING_CONDITION` Job Status

**Files:**
- Modify: `backend/app/services/queue_job.py:18-28`
- Modify: `backend/app/core/constants.py` (if status strings referenced)

**Step 1: Add the new enum value**

In `backend/app/services/queue_job.py`, add to the `JobStatus` enum:

```python
class JobStatus(Enum):
    """Status of a queue job"""
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_CONDITION = "awaiting_condition"  # NEW: AI done, waiting for user condition pick
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"
    SCHEDULED = "scheduled"
    NEEDS_REVIEW = "needs_review"
    PENDING_REVIEW = "pending_review"
```

**Step 2: Verify no hardcoded status strings break**

Run: `grep -rn "awaiting_condition\|AWAITING_CONDITION" backend/`
Expected: Only the new enum definition. No breakage.

**Step 3: Commit**

```bash
git add backend/app/services/queue_job.py
git commit -m "feat: add AWAITING_CONDITION job status for two-phase pipeline"
```

---

## Task 2: Add Valid Conditions API Endpoint

**Files:**
- Modify: `backend/app/blueprints/api/lookup_api.py`
- Existing: `backend/app/services/ebay/taxonomy.py:306-341` (already has `get_valid_condition_ids()`)

The taxonomy module already fetches valid condition IDs per category. We need an API endpoint so the frontend can request them.

**Step 1: Write the failing test**

Create `tests/unit/test_valid_conditions_api.py`:

```python
"""Tests for the valid conditions API endpoint."""
import pytest
from unittest.mock import patch


class TestValidConditionsEndpoint:
    """Test GET /api/lookup/category/<id>/conditions"""

    @patch('backend.app.services.ebay.taxonomy.get_valid_condition_ids')
    def test_returns_valid_conditions(self, mock_get_ids, client):
        mock_get_ids.return_value = ['1000', '1500', '3000', '5000']
        resp = client.get('/api/lookup/category/175673/conditions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['category_id'] == '175673'
        assert '1000' in data['condition_ids']
        assert len(data['conditions']) == 4
        # Each condition should have id and label
        assert all('id' in c and 'label' in c for c in data['conditions'])

    def test_missing_category_returns_400(self, client):
        resp = client.get('/api/lookup/category//conditions')
        assert resp.status_code == 404  # Flask route won't match empty param

    @patch('backend.app.services.ebay.taxonomy.get_valid_condition_ids')
    def test_unknown_category_returns_empty(self, mock_get_ids, client):
        mock_get_ids.return_value = []
        resp = client.get('/api/lookup/category/999999/conditions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['condition_ids'] == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_valid_conditions_api.py -v`
Expected: FAIL with 404 (endpoint doesn't exist yet)

**Step 3: Implement the endpoint**

Add to `backend/app/blueprints/api/lookup_api.py`:

```python
@lookup_bp.route('/lookup/category/<category_id>/conditions', methods=['GET'])
def get_valid_conditions(category_id):
    """Return valid eBay condition IDs and labels for a category."""
    from backend.app.services.ebay.taxonomy import get_valid_condition_ids
    from backend.app.core.constants import CONDITION_ID_MAP

    valid_ids = get_valid_condition_ids(category_id)

    # Build reverse map: condition_id -> display label
    id_to_label = {str(v): k.replace('_', ' ').title() for k, v in CONDITION_ID_MAP.items()}

    conditions = []
    for cid in valid_ids:
        conditions.append({
            'id': cid,
            'label': id_to_label.get(cid, f'Condition {cid}')
        })

    return jsonify({
        'category_id': category_id,
        'condition_ids': valid_ids,
        'conditions': conditions
    })
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_valid_conditions_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/blueprints/api/lookup_api.py tests/unit/test_valid_conditions_api.py
git commit -m "feat: add GET /api/lookup/category/<id>/conditions endpoint"
```

---

## Task 3: Split Pipeline — Phase 1 Stops at `awaiting_condition`

**Files:**
- Modify: `backend/app/services/processor_service.py:260-509` (`create_listing` method)
- Test: `tests/unit/test_pipeline_split.py` (new)

The current `create_listing()` method does everything in one pass. We split it so that when no user condition is provided, it stops after AI + comp fetching and returns `awaiting_condition` status. The comps are saved to `job.ai_data` for later use.

**Step 1: Write the failing test**

Create `tests/unit/test_pipeline_split.py`:

```python
"""Tests for two-phase pipeline split."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestPipelineSplit:
    """Pipeline should stop at awaiting_condition when no condition is set."""

    @patch('backend.app.services.processor_service.ProcessorService._validate_and_enrich_specifics')
    @patch('backend.app.services.processor_service.ProcessorService._refine_condition_from_ai')
    @patch('backend.app.services.listing_ai_agent.ListingAIAgent.analyze_item')
    def test_no_condition_returns_awaiting(self, mock_analyze, mock_refine, mock_enrich):
        """Job with no user_condition should pause at awaiting_condition."""
        from backend.app.services.processor_service import ProcessorService

        mock_analyze.return_value = {
            'success': True, 'ai_data': {'listing': {'suggested_title': 'Test'}},
            'title': 'Test Item', 'raw_description': 'Desc',
            'item_specifics': {}, 'ai_suggested_price': 25.0,
            'shipping_cost': 6.50, 'category_id': '175673',
            'confidence_score': 0.9
        }
        mock_refine.return_value = None  # No condition determined
        mock_enrich.return_value = []

        job = MagicMock()
        job.folder_path = str(Path(__file__).parent / 'fixtures')
        job.user_condition = None
        job.user_title = None
        job.user_price = None
        job.user_description = None
        job.job_metadata = {}
        job.ai_data = {}
        job.scheduled_time = None
        job.confidence_score = 0

        # Need images directory to exist with at least one image
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]):
            processor = ProcessorService()
            result = processor.create_listing(job)

        assert result['status'] == 'awaiting_condition'
        assert result['success'] is True
        assert 'category_id' in result

    @patch('backend.app.services.processor_service.ProcessorService._validate_and_enrich_specifics')
    @patch('backend.app.services.processor_service.ProcessorService._refine_condition_from_ai')
    @patch('backend.app.services.listing_ai_agent.ListingAIAgent.analyze_item')
    def test_with_condition_proceeds_normally(self, mock_analyze, mock_refine, mock_enrich):
        """Job with user_condition should proceed through full pipeline."""
        from backend.app.services.processor_service import ProcessorService

        mock_analyze.return_value = {
            'success': True, 'ai_data': {'listing': {'suggested_title': 'Test'}},
            'title': 'Test Item', 'raw_description': 'Desc',
            'item_specifics': {}, 'ai_suggested_price': 25.0,
            'shipping_cost': 6.50, 'category_id': '175673',
            'confidence_score': 0.9
        }
        mock_refine.return_value = 'USED_GOOD'
        mock_enrich.return_value = []

        job = MagicMock()
        job.folder_path = str(Path(__file__).parent / 'fixtures')
        job.user_condition = 'USED_GOOD'
        job.user_title = None
        job.user_price = None
        job.user_description = None
        job.job_metadata = {}
        job.ai_data = {}
        job.scheduled_time = None
        job.confidence_score = 0

        # With condition set, pipeline should NOT return awaiting_condition
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.iterdir', return_value=[MagicMock(suffix='.jpg')]):
            processor = ProcessorService()
            result = processor.create_listing(job)

        assert result.get('status') != 'awaiting_condition'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline_split.py -v`
Expected: FAIL (pipeline doesn't check for missing condition yet)

**Step 3: Implement the pipeline split**

Modify `backend/app/services/processor_service.py`, in `create_listing()`. After step 4c (aspect enrichment, line ~358) and before step 5 (pricing), add the condition gate:

```python
        # --- PHASE 1 GATE: Pause if no condition determined ---
        # If neither user, metadata, folder, nor AI provided a condition,
        # pause here and ask the user to pick from valid options.
        if not condition:
            _log("No condition determined — pausing for user input", level='warning')

            # Save everything computed so far to ai_data
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

Also modify `_refine_condition_from_ai()` to return `None` (instead of the DEFAULT_CONDITION fallback) when no condition source exists and `user_condition` is empty. Currently it falls back to `DEFAULT_CONDITION` from `.env`. We want it to return `None` so the gate above triggers. The existing fallback behavior is preserved when the pipeline resumes with a user-picked condition.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pipeline_split.py -v`
Expected: PASS

**Step 5: Run existing tests to verify no regression**

Run: `pytest tests/unit/ -v --tb=short`
Expected: All 282+ tests PASS

**Step 6: Commit**

```bash
git add backend/app/services/processor_service.py tests/unit/test_pipeline_split.py
git commit -m "feat: split pipeline - phase 1 pauses at awaiting_condition when no condition"
```

---

## Task 4: Add Resume Pipeline Endpoint

**Files:**
- Modify: `backend/app/blueprints/api/jobs_api.py`
- Modify: `backend/app/services/queue_manager.py` (resume logic)
- Test: `tests/unit/test_resume_pipeline.py` (new)

After the user picks a condition, the frontend POSTs to a new endpoint that sets the condition and resumes processing from phase 2 (pricing + eBay submission).

**Step 1: Write the failing test**

Create `tests/unit/test_resume_pipeline.py`:

```python
"""Tests for the resume-with-condition endpoint."""
import pytest
from unittest.mock import patch, MagicMock


class TestResumeWithCondition:
    """Test POST /api/job/<id>/set-condition"""

    @patch('backend.app.services.queue_manager.QueueManager.resume_with_condition')
    def test_set_condition_and_resume(self, mock_resume, client):
        mock_resume.return_value = {'success': True, 'status': 'processing'}
        resp = client.post('/api/job/abc123/set-condition', json={
            'condition': 'USED_GOOD'
        })
        assert resp.status_code == 200
        mock_resume.assert_called_once_with('abc123', 'USED_GOOD')

    def test_missing_condition_returns_400(self, client):
        resp = client.post('/api/job/abc123/set-condition', json={})
        assert resp.status_code == 400

    @patch('backend.app.services.queue_manager.QueueManager.resume_with_condition')
    def test_batch_set_condition(self, mock_resume, client):
        """POST /api/jobs/batch-set-condition for multiple items at once."""
        mock_resume.return_value = {'success': True}
        resp = client.post('/api/jobs/batch-set-condition', json={
            'items': [
                {'job_id': 'abc', 'condition': 'USED_GOOD'},
                {'job_id': 'def', 'condition': 'NEW'},
            ]
        })
        assert resp.status_code == 200
        assert mock_resume.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_resume_pipeline.py -v`
Expected: FAIL (endpoints don't exist)

**Step 3: Implement the endpoints**

Add to `backend/app/blueprints/api/jobs_api.py`:

```python
@jobs_bp.route('/job/<job_id>/set-condition', methods=['POST'])
def set_condition(job_id):
    """Set condition on an awaiting_condition job and resume pipeline."""
    data = request.get_json() or {}
    condition = data.get('condition')
    if not condition:
        return error_response('condition is required', 400)

    from backend.app.core.validator import validate_condition
    valid = validate_condition(condition)
    if not valid.get('valid'):
        return error_response(f"Invalid condition: {valid.get('error')}", 400)

    qm = current_app.config.get('queue_manager')
    result = qm.resume_with_condition(job_id, condition)
    if not result.get('success'):
        return error_response(result.get('error', 'Resume failed'), 400)
    return jsonify(result)


@jobs_bp.route('/jobs/batch-set-condition', methods=['POST'])
def batch_set_condition():
    """Set conditions for multiple awaiting_condition jobs."""
    data = request.get_json() or {}
    items = data.get('items', [])
    if not items:
        return error_response('items array is required', 400)

    qm = current_app.config.get('queue_manager')
    results = []
    for item in items:
        job_id = item.get('job_id')
        condition = item.get('condition')
        if job_id and condition:
            r = qm.resume_with_condition(job_id, condition)
            results.append({'job_id': job_id, **r})
    return jsonify({'results': results})
```

**Step 4: Implement `resume_with_condition` in QueueManager**

Add to `backend/app/services/queue_manager.py`:

```python
def resume_with_condition(self, job_id: str, condition: str) -> dict:
    """Resume an awaiting_condition job with the user's chosen condition.

    Sets user_condition on the job, changes status back to pending,
    and re-queues it for processing. Phase 2 of the pipeline will
    pick up the condition and skip the already-completed AI analysis.
    """
    job = self._get_job(job_id)
    if not job:
        return {'success': False, 'error': 'Job not found'}
    if job.status != 'awaiting_condition':
        return {'success': False, 'error': f'Job is {job.status}, not awaiting_condition'}

    job.user_condition = condition
    job.status = 'pending'
    self._save_job(job)
    self.emit_event('job_update', job.to_dict())

    # Re-queue for processing (phase 2 will use cached AI data)
    if not self.is_processing():
        self.start_processing()

    return {'success': True, 'status': 'pending'}
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_resume_pipeline.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/blueprints/api/jobs_api.py backend/app/services/queue_manager.py tests/unit/test_resume_pipeline.py
git commit -m "feat: add set-condition endpoint to resume awaiting_condition jobs"
```

---

## Task 5: Condition-Aware Comp Pricing

**Files:**
- Modify: `backend/app/services/pricing_engine.py:297-410` (`calculate_suggested_price`)
- Test: `tests/unit/test_condition_comp_pricing.py` (new)

Replace the static multiplier approach with same-condition comp filtering. Cascade: (1) filter comps to matching condition, (2) Gemini adjustment if too few, (3) static multiplier as last resort.

**Step 1: Write the failing test**

Create `tests/unit/test_condition_comp_pricing.py`:

```python
"""Tests for condition-aware comp pricing."""
import pytest
from unittest.mock import patch, MagicMock


class TestConditionCompPricing:
    """Pricing should prefer same-condition comps over static multipliers."""

    def _make_comp(self, price, condition):
        return {'price': price, 'condition': condition, 'title': 'Test'}

    def test_same_condition_comps_used_directly(self):
        """When 3+ comps match condition, use their median directly."""
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()

        comps = [
            self._make_comp(20.0, 'Used - Good'),
            self._make_comp(25.0, 'Used - Good'),
            self._make_comp(30.0, 'Used - Good'),
            self._make_comp(50.0, 'New'),  # Different condition, should be filtered out
        ]

        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )

        # Should use median of same-condition comps (25.0), NOT all comps
        assert 24.0 <= result['suggested_price'] <= 26.0
        assert result.get('pricing_method') == 'same_condition_comps'

    def test_few_same_condition_falls_back_to_relative(self):
        """When < 3 same-condition comps, use relative multiplier on all comps."""
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()

        comps = [
            self._make_comp(20.0, 'Used - Good'),  # Only 1 match
            self._make_comp(50.0, 'New'),
            self._make_comp(48.0, 'New'),
            self._make_comp(45.0, 'New - Open Box'),
        ]

        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )

        # Should NOT use the single comp's price directly
        # Should use relative multiplier approach
        assert result.get('pricing_method') in ('relative_multiplier', 'ai_adjusted')

    def test_no_comps_uses_static_fallback(self):
        """When no comp condition data available, fall back to static multiplier."""
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()

        comps = [
            {'price': 30.0, 'title': 'Test'},  # No condition field
            {'price': 35.0, 'title': 'Test'},
        ]

        result = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )

        assert result.get('pricing_method') == 'static_multiplier'

    def test_shipping_buffer_still_applied(self):
        """Free shipping buffer should be added after condition pricing."""
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine()

        comps = [
            self._make_comp(20.0, 'Used - Good'),
            self._make_comp(25.0, 'Used - Good'),
            self._make_comp(30.0, 'Used - Good'),
        ]

        result_no_ship = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=0
        )
        result_with_ship = engine.calculate_suggested_price(
            sold_items=comps, our_condition='Used - Good', shipping_cost=6.50
        )

        assert result_with_ship['suggested_price'] == pytest.approx(
            result_no_ship['suggested_price'] + 6.50, abs=0.50
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_condition_comp_pricing.py -v`
Expected: FAIL (current code doesn't filter comps by condition)

**Step 3: Implement condition-aware pricing**

Modify `backend/app/services/pricing_engine.py`, replace the multiplier logic in `calculate_suggested_price()` (lines ~346-384) with:

```python
        # --- Condition-Aware Pricing (3-tier cascade) ---
        MIN_SAME_CONDITION_COMPS = 3

        # Tier 1: Filter comps to same condition
        from backend.app.core.constants import CONDITION_ENUM_TO_DISPLAY
        cond_key = our_condition
        if cond_key in CONDITION_ENUM_TO_DISPLAY:
            cond_key = CONDITION_ENUM_TO_DISPLAY[cond_key]
        if "new old stock" in cond_key.lower() or "nos" in cond_key.lower():
            cond_key = "New Old Stock"

        same_condition_prices = []
        for item in sold_items:
            comp_cond = item.get("condition", "")
            comp_mult = self._resolve_condition_multiplier(comp_cond)
            our_mult = self.CONDITION_MULTIPLIERS.get(cond_key, 0.75)
            # Match if same multiplier tier (exact condition match)
            if comp_mult is not None and abs(comp_mult - our_mult) < 0.05:
                same_condition_prices.append(item['price'])

        if len(same_condition_prices) >= MIN_SAME_CONDITION_COMPS:
            # Tier 1: Enough same-condition comps — use their median directly
            base_price = statistics.median(same_condition_prices)
            multiplier = 1.0  # No adjustment needed, comps ARE our condition
            pricing_method = 'same_condition_comps'
            reasoning_prefix = f"Median of {len(same_condition_prices)} same-condition comps"
        else:
            # Tier 2: Not enough same-condition comps — use relative multiplier
            our_multiplier = self.CONDITION_MULTIPLIERS.get(cond_key, 0.75)
            comp_multipliers = []
            for item in sold_items:
                comp_cond = item.get("condition", "")
                comp_mult = self._resolve_condition_multiplier(comp_cond)
                if comp_mult is not None:
                    comp_multipliers.append(comp_mult)

            if comp_multipliers:
                avg_comp_multiplier = statistics.mean(comp_multipliers)
                multiplier = our_multiplier / avg_comp_multiplier if avg_comp_multiplier > 0 else our_multiplier
                multiplier = max(0.40, min(1.30, multiplier))
                pricing_method = 'relative_multiplier'
                reasoning_prefix = f"{reasoning_prefix} (relative condition adj {multiplier:.2f}x)"
            else:
                # Tier 3: No condition data on comps at all — static fallback
                multiplier = our_multiplier
                pricing_method = 'static_multiplier'
                reasoning_prefix = f"{reasoning_prefix} (static {cond_key} {multiplier}x)"

        # Calculate suggested price
        suggested_price = round(base_price * multiplier, 2)
```

Also add `pricing_method` to the return dict.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_condition_comp_pricing.py -v`
Expected: PASS

**Step 5: Run existing pricing tests for regression**

Run: `pytest tests/unit/test_pricing_engine.py tests/unit/test_research_pricing.py -v`
Expected: All PASS (may need minor assertion updates if return shape changed)

**Step 6: Commit**

```bash
git add backend/app/services/pricing_engine.py tests/unit/test_condition_comp_pricing.py
git commit -m "feat: condition-aware comp pricing - filter by same condition before static multiplier"
```

---

## Task 6: Frontend — Condition Review Screen

**Files:**
- Create: `frontend/src/components/ConditionReview.tsx`
- Modify: `frontend/src/App.tsx` (replace QuickListingForm tab)
- Modify: `frontend/src/store/useCommanderStore.ts` (add awaiting jobs tracking)
- Modify: `frontend/src/lib/api.ts` (add API calls)
- Delete: `frontend/src/components/PhotoEditor.tsx`
- Delete: `frontend/src/components/QuickListingForm.tsx`

**Step 1: Add API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
export interface ConditionOption {
    id: string
    label: string
}

export async function fetchValidConditions(categoryId: string): Promise<ConditionOption[]> {
    const data = await apiFetch<{ conditions: ConditionOption[] }>(
        `/api/lookup/category/${categoryId}/conditions`
    )
    return data.conditions
}

export async function setJobCondition(jobId: string, condition: string): Promise<void> {
    await apiFetch(`/api/job/${jobId}/set-condition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ condition })
    })
}

export async function batchSetCondition(
    items: Array<{ job_id: string; condition: string }>
): Promise<void> {
    await apiFetch('/api/jobs/batch-set-condition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
    })
}
```

**Step 2: Create ConditionReview component**

Create `frontend/src/components/ConditionReview.tsx`:

A swipeable card-based UI showing jobs in `awaiting_condition` status. Each card shows:
- Thumbnail (first image from job)
- AI-generated title
- Category badge
- Condition picker (Select dropdown) with only valid conditions for that category
- Submit button

Key implementation details:
- Fetch valid conditions from `/api/lookup/category/<id>/conditions` per job
- Cache conditions by category_id (many items share categories)
- "Submit All" button for batch operation
- Empty state: "No items waiting for condition" with link back to dashboard
- Mobile-first: full-width cards, large touch targets, swipe between items

```typescript
// Component skeleton — implementer fills in full UI
import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCommanderStore } from '@/store/useCommanderStore'
import { fetchValidConditions, setJobCondition, batchSetCondition, type ConditionOption } from '@/lib/api'
import { toast } from 'sonner'

export function ConditionReview() {
    const jobs = useCommanderStore(s => s.jobs)
    const awaitingJobs = jobs.filter(j => j.status === 'awaiting_condition')

    // State: { [jobId]: selectedCondition }
    const [selections, setSelections] = useState<Record<string, string>>({})
    // Cache: { [categoryId]: ConditionOption[] }
    const [conditionCache, setConditionCache] = useState<Record<string, ConditionOption[]>>({})

    // Fetch valid conditions for each unique category
    useEffect(() => {
        const categoryIds = [...new Set(awaitingJobs.map(j => j.ai_data?.category_id).filter(Boolean))]
        categoryIds.forEach(async (catId) => {
            if (!conditionCache[catId]) {
                const conditions = await fetchValidConditions(catId)
                setConditionCache(prev => ({ ...prev, [catId]: conditions }))
            }
        })
    }, [awaitingJobs])

    const handleSubmitAll = async () => {
        const items = Object.entries(selections).map(([job_id, condition]) => ({
            job_id, condition
        }))
        if (items.length === 0) {
            toast.error('Select conditions first')
            return
        }
        await batchSetCondition(items)
        toast.success(`${items.length} items queued for listing`)
    }

    // ... render cards with condition select per job
}
```

**Step 3: Update store to track awaiting count**

Add to `frontend/src/store/useCommanderStore.ts` a derived getter:

```typescript
// In the CommanderState interface, no change needed —
// awaitingJobs is derived from jobs.filter(j => j.status === 'awaiting_condition')
// The existing jobs array + Socket.IO updates will keep this current.
```

**Step 4: Wire into App.tsx**

In `frontend/src/App.tsx`:
- Remove imports: `QuickListingForm`, `PhotoEditor`
- Add import: `ConditionReview`
- Replace `{activeTab === 'create' && <QuickListingForm />}` with `{activeTab === 'condition-review' && <ConditionReview />}`
- Remove the `photo-editor` tab block entirely
- Add badge to sidebar/nav showing count of `awaiting_condition` jobs

**Step 5: Delete dead components**

```bash
rm frontend/src/components/PhotoEditor.tsx
rm frontend/src/components/QuickListingForm.tsx
```

**Step 6: Build and verify**

Run: `cd frontend && npm run build`
Expected: Clean build, no TypeScript errors

**Step 7: Commit**

```bash
git add frontend/src/components/ConditionReview.tsx frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/store/useCommanderStore.ts
git rm frontend/src/components/PhotoEditor.tsx frontend/src/components/QuickListingForm.tsx
git commit -m "feat: condition review screen replaces dead QuickListingForm + PhotoEditor"
```

---

## Task 7: Socket.IO — Notify Frontend When Jobs Await Condition

**Files:**
- Modify: `backend/app/services/queue_manager.py` (emit on status change)
- Modify: `frontend/src/hooks/useJobSync.ts` (handle new status)

**Step 1: Backend — emit job_update with awaiting_condition status**

The existing `emit_event('job_update', job.to_dict())` already fires on status changes. Since the pipeline returns `status: 'awaiting_condition'` and the queue manager updates the job status, this should work automatically.

Verify in `queue_manager.py` that after `create_listing()` returns with `status == 'awaiting_condition'`, the job status is updated and emitted:

```python
# In the job processing loop, after create_listing returns:
if result.get('status') == 'awaiting_condition':
    job.status = 'awaiting_condition'
    self._save_job(job)
    self.emit_event('job_update', job.to_dict())
    # Don't mark as failed — it's waiting for user input
    continue
```

**Step 2: Frontend — useJobSync already handles job_update**

The existing `useJobSync` hook listens for `job_update` events and updates the Zustand store. Since `awaiting_condition` is just another status string, the frontend will automatically reflect it. No changes needed in useJobSync.

**Step 3: Add notification badge**

In the sidebar/MobileNavBar, show a badge count on the "Condition Review" tab:

```typescript
const awaitingCount = jobs.filter(j => j.status === 'awaiting_condition').length
// Render badge on tab: {awaitingCount > 0 && <Badge>{awaitingCount}</Badge>}
```

**Step 4: Commit**

```bash
git add backend/app/services/queue_manager.py frontend/src/App.tsx
git commit -m "feat: socket.io notification + badge for awaiting_condition jobs"
```

---

## Task 8: Fix XSS in Book Lookup

**Files:**
- Modify: `backend/app/blueprints/api/lookup_api.py:44`
- Test: `tests/unit/test_xss_book_lookup.py` (new)

**Step 1: Write the failing test**

Create `tests/unit/test_xss_book_lookup.py`:

```python
"""Test XSS prevention in book lookup."""
import pytest
from unittest.mock import patch, MagicMock
import html


class TestBookLookupXSS:
    @patch('backend.app.blueprints.api.lookup_api.PricingEngine')
    @patch('backend.app.blueprints.api.lookup_api.BookService')
    def test_html_escaped_in_description(self, MockBook, MockPricing, client):
        MockBook.return_value.lookup_isbn.return_value = {
            'success': True,
            'title': '<script>alert("xss")</script>',
            'authors': ['<img onerror=alert(1) src=x>'],
            'publisher': '<b>Evil</b>',
            'publishedDate': '2020',
            'description': '<script>steal()</script>',
        }
        MockPricing.return_value.get_price_with_comps.return_value = {'suggested_price': 10}

        resp = client.get('/api/lookup/book?isbn=9780123456789')
        data = resp.get_json()
        desc = data['description']

        assert '<script>' not in desc
        assert '&lt;script&gt;' in desc
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_xss_book_lookup.py -v`
Expected: FAIL (script tag appears unescaped)

**Step 3: Fix — add html.escape()**

In `backend/app/blueprints/api/lookup_api.py`, add `import html` at top and change line 44:

```python
"description": f"<h2>{html.escape(title)}</h2><p><b>Author:</b> {html.escape(authors)}<br><b>Publisher:</b> {html.escape(str(book_data.get('publisher', '')))}<br><b>Year:</b> {html.escape(str(book_data.get('publishedDate', '')))}</p><p>{html.escape(str(book_data.get('description', '')))}</p>",
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_xss_book_lookup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/blueprints/api/lookup_api.py tests/unit/test_xss_book_lookup.py
git commit -m "fix: escape HTML in book lookup to prevent XSS"
```

---

## Task 9: Fix Silent .env Failure

**Files:**
- Modify: `backend/config.py:40-41`

**Step 1: Replace silent exception with logged warning**

Change lines 40-41 in `backend/config.py` from:

```python
    except Exception:
        pass  # Fail silently in config loader to prevent startup crashes
```

To:

```python
    except FileNotFoundError:
        pass  # No .env file found — rely on environment variables
    except Exception as e:
        import sys
        print(f"WARNING: Failed to load .env file: {e}", file=sys.stderr)
```

**Step 2: Add startup validation in create_app()**

In `backend/app/__init__.py`, after `create_app()` configures the app, add a check:

```python
# Validate critical config
required_keys = ['EBAY_APP_ID', 'EBAY_CERT_ID']
missing = [k for k in required_keys if not os.environ.get(k)]
if missing:
    logger.warning(f"Missing environment variables: {', '.join(missing)}. eBay features will be disabled.")
```

**Step 3: Commit**

```bash
git add backend/config.py backend/app/__init__.py
git commit -m "fix: log warning on .env load failure instead of silent pass"
```

---

## Task 10: Fix Integration Test Failures

**Files:**
- Modify: `tests/integration/test_full_pipeline.py`
- Modify: `tests/integration/test_smart_pricing.py`

The 3 full pipeline tests fail because `create_listing()` now returns `awaiting_condition` when no explicit condition is set. The test needs to provide a condition.

**Step 1: Update test fixtures to include condition**

In `test_full_pipeline.py`, modify `_run_pipeline()` around line 142:

```python
job = _create_job_obj(job_id, temp_folder, scheduled_time=schedule_time)
job.user_condition = 'USED_GOOD'  # Provide condition so pipeline completes
```

**Step 2: Fix smart pricing NOS test**

In `test_smart_pricing.py`, the `test_condition_multiplier_nos` test expects `0.95` but gets `0.9`. Check if the NOS multiplier value changed or if the relative multiplier logic altered the result. Adjust the assertion to match the new pricing logic.

**Step 3: Run all integration tests**

Run: `pytest tests/integration/ -v`
Expected: All 15 PASS

**Step 4: Commit**

```bash
git add tests/integration/test_full_pipeline.py tests/integration/test_smart_pricing.py
git commit -m "fix: update integration tests for two-phase pipeline"
```

---

## Task 11: Git Cleanup

**Files:**
- Delete: `backup_claude.md`, `master_claude.md`, `nul`
- Gitignore: `data/*.corrupt.*`, `data/*_dump.sql`, `data/*_recover.sql`

**Step 1: Remove stale files**

```bash
rm -f backup_claude.md master_claude.md nul
rm -f data/commander.db.corrupt.* data/commander_dump.sql data/commander_recover.sql
```

**Step 2: Update .gitignore**

Add to `.gitignore`:

```
data/*.corrupt.*
data/*_dump.sql
data/*_recover.sql
nul
```

**Step 3: Build frontend and commit clean static assets**

```bash
cd frontend && npm run build && cd ..
git add -A static/app/
git add .gitignore
git commit -m "chore: clean stale files, update .gitignore, rebuild frontend"
```

---

## Task Summary

| # | Task | Type | Est. Complexity |
|---|------|------|----------------|
| 1 | Add AWAITING_CONDITION status | Backend | Trivial |
| 2 | Valid conditions API endpoint | Backend + Test | Small |
| 3 | Split pipeline at condition gate | Backend + Test | Medium |
| 4 | Resume pipeline endpoint | Backend + Test | Medium |
| 5 | Condition-aware comp pricing | Backend + Test | Medium |
| 6 | Condition Review screen (frontend) | Frontend | Large |
| 7 | Socket.IO notifications + badge | Full-stack | Small |
| 8 | Fix XSS in book lookup | Backend + Test | Trivial |
| 9 | Fix silent .env failure | Backend | Trivial |
| 10 | Fix integration tests | Tests | Small |
| 11 | Git cleanup | Housekeeping | Trivial |

**Dependency order:** 1 → 3 → 4 → 7 (backend chain), 2 → 6 (frontend chain), 5 (independent), 8-11 (independent fixes). Tasks 5, 8, 9, 11 can run in parallel with anything.
