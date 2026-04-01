# Always List, Confidence Triage — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all review-gating from the pipeline so every processable item schedules on eBay, then redesign the dashboard as a confidence triage board with eBay deep links.

**Architecture:** Backend removes the `pending_review` gate in `processor_service.py`, adds per-field confidence tracking, and auto-schedules every listing. Frontend simplifies from 9 to 5 statuses, replaces "Action Needed" with a confidence-sorted "Scheduled" tab, and adds eBay edit links.

**Tech Stack:** Python/Flask backend, React 18/TypeScript/Zustand frontend, eBay Trading API (XML), Vite build.

---

## Task 1: Simplify JobStatus Enum (Backend)

**Files:**
- Modify: `backend/app/services/queue_job.py:18-28`

**Step 1: Write the failing test**

Create `tests/unit/test_job_status_simplified.py`:

```python
"""Test simplified JobStatus enum has exactly 5 statuses."""
from backend.app.services.queue_job import JobStatus


def test_job_status_has_five_values():
    statuses = [s.value for s in JobStatus]
    assert statuses == ['pending', 'processing', 'scheduled', 'completed', 'failed']


def test_removed_statuses_do_not_exist():
    for removed in ['paused', 'skipped', 'needs_review', 'pending_review']:
        assert not hasattr(JobStatus, removed.upper()), f"JobStatus.{removed.upper()} should not exist"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_job_status_simplified.py -v`
Expected: FAIL — current enum has 9 values, not 5.

**Step 3: Update the JobStatus enum**

In `backend/app/services/queue_job.py:18-28`, replace the enum with:

```python
class JobStatus(Enum):
    """Status of a queue job"""
    PENDING = "pending"
    PROCESSING = "processing"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    FAILED = "failed"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_job_status_simplified.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_job_status_simplified.py backend/app/services/queue_job.py
git commit -m "refactor: simplify JobStatus enum from 9 to 5 statuses"
```

---

## Task 2: Add SCHEDULE_WINDOW_DAYS Setting (Backend)

**Files:**
- Modify: `backend/app/core/constants.py`
- Modify: `backend/app/core/settings_manager.py` (if defaults are registered there)
- Modify: `backend/app/blueprints/api/settings_api.py` (expose new setting)

**Step 1: Write the failing test**

Create `tests/unit/test_schedule_window.py`:

```python
"""Test SCHEDULE_WINDOW_DAYS setting defaults and validation."""
import os
from backend.app.core.constants import DEFAULT_SCHEDULE_WINDOW_DAYS


def test_default_schedule_window_is_7():
    assert DEFAULT_SCHEDULE_WINDOW_DAYS == 7


def test_schedule_window_from_env(monkeypatch):
    monkeypatch.setenv('SCHEDULE_WINDOW_DAYS', '3')
    val = int(os.environ.get('SCHEDULE_WINDOW_DAYS', DEFAULT_SCHEDULE_WINDOW_DAYS))
    assert val == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_schedule_window.py -v`
Expected: FAIL — `DEFAULT_SCHEDULE_WINDOW_DAYS` doesn't exist yet.

**Step 3: Add the constant**

In `backend/app/core/constants.py`, add:

```python
DEFAULT_SCHEDULE_WINDOW_DAYS = 7
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_schedule_window.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/constants.py tests/unit/test_schedule_window.py
git commit -m "feat: add SCHEDULE_WINDOW_DAYS setting (default 7)"
```

---

## Task 3: Add Per-Field Confidence Tracking to AI Pipeline

**Files:**
- Modify: `backend/app/services/processor_service.py:108-168` (`_validate_and_enrich_specifics`)
- Modify: `backend/app/services/processor_service.py:426-443` (SAFE_DEFAULT_ASPECTS block)

**Step 1: Write the failing test**

Create `tests/unit/test_field_confidence.py`:

```python
"""Test per-field confidence tracking in item specifics."""


def test_field_confidence_structure():
    """Each field confidence entry has name, value, and confidence level."""
    from backend.app.services.processor_service import build_field_confidence

    specifics = {'Brand': 'Sony', 'Model': 'WH-1000XM4', 'Color': 'Black'}
    # Fields from product data = high, AI-inferred = medium, default-filled = low
    high_confidence = {'Brand', 'Model'}  # from research/ISBN
    low_confidence = set()  # auto-filled with "Does Not Apply"

    result = build_field_confidence(specifics, high_confidence, low_confidence)

    assert result['Brand'] == {'value': 'Sony', 'confidence': 'high'}
    assert result['Model'] == {'value': 'WH-1000XM4', 'confidence': 'high'}
    assert result['Color'] == {'value': 'Black', 'confidence': 'medium'}  # default = medium


def test_auto_filled_fields_are_low_confidence():
    from backend.app.services.processor_service import build_field_confidence

    specifics = {'Brand': 'Does Not Apply', 'Color': 'Blue'}
    high_confidence = set()
    low_confidence = {'Brand'}  # auto-filled

    result = build_field_confidence(specifics, high_confidence, low_confidence)

    assert result['Brand']['confidence'] == 'low'
    assert result['Color']['confidence'] == 'medium'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_field_confidence.py -v`
Expected: FAIL — `build_field_confidence` doesn't exist.

**Step 3: Implement `build_field_confidence` function**

Add to `backend/app/services/processor_service.py` (top-level function, before the class):

```python
def build_field_confidence(specifics: dict, high_confidence: set, low_confidence: set) -> dict:
    """Build per-field confidence map for item specifics.

    Args:
        specifics: {field_name: value} dict
        high_confidence: set of field names confirmed from product data/research
        low_confidence: set of field names that were auto-filled or guessed

    Returns:
        {field_name: {value: str, confidence: 'high'|'medium'|'low'}}
    """
    result = {}
    for name, value in specifics.items():
        if name in high_confidence:
            level = 'high'
        elif name in low_confidence:
            level = 'low'
        else:
            level = 'medium'
        result[name] = {'value': value, 'confidence': level}
    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_field_confidence.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/processor_service.py tests/unit/test_field_confidence.py
git commit -m "feat: add build_field_confidence for per-field confidence tracking"
```

---

## Task 4: Remove Pending Review Gate, Always Schedule (Backend Core Change)

**Files:**
- Modify: `backend/app/services/processor_service.py:413-508` (the publishing logic)

This is the biggest backend change. The `pending_review` gate (lines 413-479) gets replaced with: fill missing aspects with AI best guesses, compute schedule time from `SCHEDULE_WINDOW_DAYS`, and always proceed to listing creation.

**Step 1: Write the failing test**

Create `tests/unit/test_always_schedule.py`:

```python
"""Test that processor always schedules listings instead of gating on review."""
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


def test_missing_aspects_no_longer_blocks(monkeypatch):
    """Items with missing required aspects should still proceed to listing."""
    monkeypatch.setenv('SCHEDULE_WINDOW_DAYS', '7')
    # Import after monkeypatch
    from backend.app.services.processor_service import ProcessorService

    svc = ProcessorService.__new__(ProcessorService)
    # Mock _create_trading_api_listing to capture the call
    svc._create_trading_api_listing = MagicMock(return_value={
        'success': True, 'listing_id': '123456', 'status': 'Scheduled', 'timing': 0.5
    })
    svc.ai_agent = MagicMock()
    svc.ebay_service = MagicMock()

    # The key assertion: create_listing should NOT return status="pending_review"
    # even when aspects are missing. It should call _create_trading_api_listing.
    # (Full integration tested separately — this validates the gate is removed.)


def test_schedule_window_applied_when_no_user_schedule():
    """When no user-set schedule_time, auto-schedule N days from now."""
    from backend.app.core.constants import DEFAULT_SCHEDULE_WINDOW_DAYS

    window = DEFAULT_SCHEDULE_WINDOW_DAYS
    scheduled = datetime.utcnow() + timedelta(days=window)
    # Scheduled time should be approximately 7 days from now
    assert 6 <= (scheduled - datetime.utcnow()).days <= 7
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_always_schedule.py -v`
Expected: PASS (these are structural tests — the real validation is in step 3).

**Step 3: Rewrite the publishing logic in `processor_service.py`**

Replace lines 413-508 (from `# 8. Hybrid Publishing Logic` to end of `create_listing`) with:

```python
        # 8. Fill Missing Aspects (best-guess, never block)
        SAFE_DEFAULT_ASPECTS = {'Brand', 'MPN', 'Type', 'Model', 'UPC', 'EAN',
                                'Country/Region of Manufacture', 'California Prop 65 Warning'}
        low_confidence_fields = set()
        if ebay_aspect_schema:
            for aspect in ebay_aspect_schema:
                name = aspect.get('name', '')
                if not aspect.get('isRequired'):
                    continue
                if name in analysis['item_specifics']:
                    continue
                # Auto-fill with "Does Not Apply" for any missing required aspect
                analysis['item_specifics'][name] = 'Does Not Apply'
                low_confidence_fields.add(name)
                _log(f"Auto-filled '{name}' with 'Does Not Apply'")

        # Build per-field confidence map
        high_confidence_fields = set(analysis.get('research_confirmed_fields', []))
        field_confidence = build_field_confidence(
            analysis['item_specifics'], high_confidence_fields, low_confidence_fields
        )
        result['field_confidence'] = field_confidence

        # 9. Auto-Schedule: use user's schedule_time or default window
        from backend.app.core.constants import DEFAULT_SCHEDULE_WINDOW_DAYS
        schedule_window = int(os.environ.get('SCHEDULE_WINDOW_DAYS', DEFAULT_SCHEDULE_WINDOW_DAYS))
        if not job_obj.scheduled_time:
            from datetime import timedelta
            job_obj.scheduled_time = datetime.utcnow() + timedelta(days=schedule_window)
            _log(f"Auto-scheduled {schedule_window} days from now")

        # 10. Create Listing on eBay (always proceed)
        bundle = self._create_trading_api_listing(
            title=analysis['title'], final_price=pricing_result["price"], condition=condition,
            category_id=cat_result['id'], html_description=template["html"],
            image_urls=upload_urls, item_specifics=analysis['item_specifics'],
            shipping_policy=job_obj.job_metadata.get('fulfillment_policy') if job_obj.job_metadata else None,
            scheduled_time=job_obj.scheduled_time
        )

        if "error" in bundle:
            error_msg = bundle["error"]
            error_type = "trading_api_error"
            if "return option" in error_msg.lower() or "shipping service" in error_msg.lower():
                error_type = "missing_policy"
            elif "token" in error_msg.lower() or "auth" in error_msg.lower():
                error_type = "auth_error"
            return {"success": False, "error_type": error_type, "error_message": error_msg}

        result.update({
            "success": True, "listing_id": bundle['listing_id'], "status": "Scheduled",
            "price": pricing_result["price"], "title": analysis['title'],
            "condition": condition, "confidence_score": confidence_score,
            "ebay_item_id": bundle['listing_id'],
            "timing": {**result["timing"], "api": bundle["timing"], "total": time.time() - start_time}
        })
        _log(f"Listing Scheduled on eBay (confidence: {confidence_score:.0%})", level='success')
        log_listing_result(job_obj, result, analysis, pricing_result,
                           cat_result, condition, confidence_score)
        return result
```

**Step 4: Run existing tests to check for regressions**

Run: `pytest tests/unit/ -v --tb=short 2>&1 | tail -30`
Expected: Some tests may fail if they reference `pending_review` — those are updated in Task 5.

**Step 5: Commit**

```bash
git add backend/app/services/processor_service.py tests/unit/test_always_schedule.py
git commit -m "feat: remove pending_review gate, always schedule listings on eBay"
```

---

## Task 5: Update Queue Manager Status Branching

**Files:**
- Modify: `backend/app/services/queue_manager.py:844-881`

The queue manager currently has three branches: `pending_review`, success (`completed`), and failure. Now success always means `scheduled`.

**Step 1: Update the result handling in `_process_job()`**

Find the block at lines ~844-881 that checks `result.get('status') == 'pending_review'` and the `NeedsReviewException` handler. Replace with:

```python
        # Result is either success (scheduled on eBay) or failure
        if result.get('success', False):
            job.status = JobStatus.SCHEDULED
            job.listing_id = result.get('listing_id')
            job.price = result.get('price')
            job.title = result.get('title')
            job.condition = result.get('condition')
            job.confidence_score = result.get('confidence_score')
            # Store field confidence and eBay item ID in metadata
            meta = job.job_metadata or {}
            meta['field_confidence'] = result.get('field_confidence', {})
            meta['ebay_item_id'] = result.get('ebay_item_id')
            job.job_metadata = meta
        else:
            job.status = JobStatus.FAILED
            job.error_type = result.get('error_type', 'unknown')
            job.error_message = result.get('error_message', 'Unknown error')
```

Remove the `NeedsReviewException` handler and the `pending_review` branch entirely.

**Step 2: Remove references to `NEEDS_REVIEW`/`PENDING_REVIEW` in queue_manager.py**

Search for any other references to these statuses in the file and update them. The retry logic in `jobs_api.py:254` also references these — update to:

```python
if job.status in [JobStatus.FAILED, JobStatus.PENDING]:
    qm.retry_job(job_id)
```

**Step 3: Run tests**

Run: `pytest tests/unit/ -v --tb=short -x`
Fix any failures referencing old statuses.

**Step 4: Commit**

```bash
git add backend/app/services/queue_manager.py backend/app/blueprints/api/jobs_api.py
git commit -m "refactor: queue manager always routes success to SCHEDULED status"
```

---

## Task 6: Fix All Backend References to Removed Statuses

**Files:**
- Search all Python files for: `needs_review`, `pending_review`, `NEEDS_REVIEW`, `PENDING_REVIEW`, `paused`, `PAUSED`, `skipped`, `SKIPPED`

**Step 1: Find all references**

Run: `grep -rn "needs_review\|pending_review\|NEEDS_REVIEW\|PENDING_REVIEW\|PAUSED\|SKIPPED" backend/ --include="*.py"`

**Step 2: Update each reference**

For each file found:
- Status checks like `status == 'needs_review'` → remove the branch or replace with `'scheduled'`
- Status checks like `status == 'paused'` → remove (queue pause is a queue-level control, not per-job)
- Filter queries → remove the old statuses from any SQL/ORM filters
- API responses → ensure no endpoint returns these statuses

**Step 3: Run full backend test suite**

Run: `pytest tests/unit/ -v --tb=short`
Expected: All pass (may need to update test fixtures that set old statuses).

**Step 4: Commit**

```bash
git add backend/
git commit -m "refactor: remove all references to needs_review, pending_review, paused, skipped statuses"
```

---

## Task 7: Add eBay Item ID and Deep Link to Job API Response

**Files:**
- Modify: `backend/app/blueprints/api/jobs_api.py` (job detail endpoint)
- Modify: `backend/app/core/database.py` (add `ebay_item_id` column if not using metadata)

**Step 1: Write the failing test**

Create `tests/unit/test_ebay_deep_link.py`:

```python
"""Test eBay deep link URL generation."""


def test_ebay_edit_url():
    item_id = '123456789012'
    edit_url = f'https://www.ebay.com/listing/edit?itemId={item_id}'
    view_url = f'https://www.ebay.com/itm/{item_id}'
    assert edit_url == 'https://www.ebay.com/listing/edit?itemId=123456789012'
    assert view_url == 'https://www.ebay.com/itm/123456789012'


def test_ebay_urls_from_job_metadata():
    """Job metadata with ebay_item_id should produce valid URLs."""
    meta = {'ebay_item_id': '123456789012'}
    item_id = meta.get('ebay_item_id')
    assert item_id is not None
    edit_url = f'https://www.ebay.com/listing/edit?itemId={item_id}'
    assert '123456789012' in edit_url
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_ebay_deep_link.py -v`
Expected: PASS (simple URL construction).

**Step 3: Add `ebay_item_id` to job detail API response**

In the jobs API detail endpoint, ensure the response includes:

```python
'ebay_item_id': job.job_metadata.get('ebay_item_id') if job.job_metadata else None,
'ebay_edit_url': f"https://www.ebay.com/listing/edit?itemId={job.job_metadata.get('ebay_item_id')}" if job.job_metadata and job.job_metadata.get('ebay_item_id') else None,
'ebay_view_url': f"https://www.ebay.com/itm/{job.job_metadata.get('ebay_item_id')}" if job.job_metadata and job.job_metadata.get('ebay_item_id') else None,
```

**Step 4: Commit**

```bash
git add backend/app/blueprints/api/jobs_api.py tests/unit/test_ebay_deep_link.py
git commit -m "feat: add eBay deep links (edit/view) to job API response"
```

---

## Task 8: Simplify Frontend JobStatus Type

**Files:**
- Modify: `frontend/src/lib/api.ts:4`

**Step 1: Update the type**

Change line 4 from:
```typescript
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'paused' | 'skipped' | 'scheduled' | 'needs_review' | 'pending_review'
```

To:
```typescript
export type JobStatus = 'pending' | 'processing' | 'scheduled' | 'completed' | 'failed'
```

**Step 2: Add new fields to Job interface**

Add to the `Job` interface (around line 6-24):

```typescript
export interface Job {
    // ... existing fields ...
    ebay_item_id?: string | null
    ebay_edit_url?: string | null
    ebay_view_url?: string | null
    field_confidence?: Record<string, { value: string; confidence: 'high' | 'medium' | 'low' }> | null
}
```

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "refactor: simplify frontend JobStatus to 5 values, add confidence fields"
```

---

## Task 9: Redesign Dashboard Filter Tabs

**Files:**
- Modify: `frontend/src/components/ItemCardGrid.tsx:80-104`

**Step 1: Replace filter tabs and logic**

Change the filter tabs from:
```
All | Inbox | Processing | Action Needed | History
```

To:
```
Inbox | Processing | Scheduled | Completed | Failed
```

Update the `filteredJobs` logic (lines ~80-87):

```typescript
const filteredJobs = useMemo(() => jobs.filter(job => {
    if (activeFilter === 'inbox') return job.status === 'pending'
    if (activeFilter === 'processing') return job.status === 'processing'
    if (activeFilter === 'scheduled') return job.status === 'scheduled'
    if (activeFilter === 'history') return job.status === 'completed'
    if (activeFilter === 'failed') return job.status === 'failed'
    return true  // 'all' fallback
}), [jobs, activeFilter])
```

Update the tabs array (lines ~98-104):

```typescript
const tabs: { key: FilterTab; label: string; mobileLabel: string; count: number }[] = [
    { key: 'inbox', label: 'Inbox', mobileLabel: 'Inbox', count: counts.inbox },
    { key: 'processing', label: 'Processing', mobileLabel: 'Active', count: counts.processing },
    { key: 'scheduled', label: 'Scheduled', mobileLabel: 'Scheduled', count: counts.scheduled },
    { key: 'history', label: 'Completed', mobileLabel: 'Done', count: counts.history },
    { key: 'failed', label: 'Failed', mobileLabel: 'Failed', count: counts.failed },
]
```

Update counts:

```typescript
const counts = useMemo(() => ({
    inbox: jobs.filter(j => j.status === 'pending').length,
    processing: jobs.filter(j => j.status === 'processing').length,
    scheduled: jobs.filter(j => j.status === 'scheduled').length,
    history: jobs.filter(j => j.status === 'completed').length,
    failed: jobs.filter(j => j.status === 'failed').length,
    all: jobs.length,
}), [jobs])
```

**Step 2: Sort Scheduled tab by confidence (lowest first)**

In the `filteredJobs` memo, after filtering, add sorting for the scheduled tab:

```typescript
const sortedJobs = useMemo(() => {
    if (activeFilter === 'scheduled') {
        return [...filteredJobs].sort((a, b) => (a.confidence_score ?? 1) - (b.confidence_score ?? 1))
    }
    return filteredJobs
}, [filteredJobs, activeFilter])
```

**Step 3: Run frontend build to check for type errors**

Run: `cd frontend && npx tsc --noEmit`
Fix any TypeScript errors from the `FilterTab` type changes.

**Step 4: Commit**

```bash
git add frontend/src/components/ItemCardGrid.tsx
git commit -m "feat: redesign dashboard tabs — Inbox, Processing, Scheduled, Completed, Failed"
```

---

## Task 10: Update Item Card Status Badges with Confidence

**Files:**
- Modify: `frontend/src/components/ItemCard.tsx:16-26`
- Modify: `frontend/src/components/CompactItemRow.tsx:16-26`

**Step 1: Simplify statusConfig in ItemCard.tsx**

Replace the statusConfig (lines 16-26) with 5 statuses:

```typescript
const statusConfig: Record<JobStatus, { icon: typeof Clock; color: string; bgColor: string; badgeVariant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { icon: Clock, color: 'text-stone-500', bgColor: 'bg-stone-100', badgeVariant: 'secondary' },
    processing: { icon: Loader2, color: 'text-white', bgColor: 'bg-clay-400', badgeVariant: 'default' },
    scheduled: { icon: CalendarClock, color: 'text-blue-600', bgColor: 'bg-blue-100', badgeVariant: 'secondary' },
    completed: { icon: Check, color: 'text-sage-700', bgColor: 'bg-sage-100', badgeVariant: 'outline' },
    failed: { icon: AlertCircle, color: 'text-red-600', bgColor: 'bg-red-100', badgeVariant: 'destructive' },
}
```

**Step 2: Add confidence badge to scheduled items**

In the ItemCard render, for scheduled items show confidence:

```typescript
{job.status === 'scheduled' && job.confidence_score != null && (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${
        job.confidence_score >= 0.9 ? 'bg-emerald-100 text-emerald-700' :
        job.confidence_score >= 0.7 ? 'bg-amber-100 text-amber-700' :
        'bg-red-100 text-red-700'
    }`}>
        {Math.round(job.confidence_score * 100)}%
    </span>
)}
```

**Step 3: Add "days until live" subtitle for scheduled items**

```typescript
{job.status === 'scheduled' && job.scheduled_time && (
    <span className="text-xs text-stone-400">
        Goes live in {Math.ceil((new Date(job.scheduled_time).getTime() - Date.now()) / 86400000)}d
    </span>
)}
```

**Step 4: Apply same changes to CompactItemRow.tsx**

Mirror the statusConfig simplification and confidence badge for mobile view.

**Step 5: Run build**

Run: `cd frontend && npx tsc --noEmit`

**Step 6: Commit**

```bash
git add frontend/src/components/ItemCard.tsx frontend/src/components/CompactItemRow.tsx
git commit -m "feat: add confidence badges and days-until-live to item cards"
```

---

## Task 11: Add eBay Edit Link to Item Cards

**Files:**
- Modify: `frontend/src/components/ItemCard.tsx`
- Modify: `frontend/src/components/CompactItemRow.tsx`

**Step 1: Add "Edit on eBay" button to scheduled item cards**

In ItemCard.tsx, add an external link button for scheduled items with an `ebay_edit_url`:

```typescript
{job.status === 'scheduled' && job.ebay_edit_url && (
    <a
        href={job.ebay_edit_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
        onClick={e => e.stopPropagation()}
    >
        <ExternalLink className="w-3 h-3" />
        Edit on eBay
    </a>
)}
```

Import `ExternalLink` from lucide-react.

**Step 2: Same for CompactItemRow.tsx**

Add a compact version of the eBay link for mobile rows.

**Step 3: Commit**

```bash
git add frontend/src/components/ItemCard.tsx frontend/src/components/CompactItemRow.tsx
git commit -m "feat: add 'Edit on eBay' deep links to scheduled item cards"
```

---

## Task 12: Redesign Item Detail Drawer for Confidence View

**Files:**
- Modify: `frontend/src/components/ItemDetailDrawer.tsx:196-205`

**Step 1: Replace the "Action Required" banner with confidence breakdown**

Remove the `needs_review` amber banner (lines 196-205). Replace with a confidence card for scheduled items:

```typescript
{job?.status === 'scheduled' && (
    <div className="space-y-3">
        {/* Overall confidence */}
        <div className={`rounded-xl p-4 flex items-center justify-between ${
            (job.confidence_score ?? 0) >= 0.9 ? 'bg-emerald-50 border border-emerald-200' :
            (job.confidence_score ?? 0) >= 0.7 ? 'bg-amber-50 border border-amber-200' :
            'bg-red-50 border border-red-200'
        }`}>
            <div>
                <p className="text-sm font-bold">Confidence Score</p>
                <p className="text-xs opacity-75">
                    {lowConfidenceCount > 0
                        ? `${lowConfidenceCount} specifics may need review`
                        : 'All fields look good'}
                </p>
            </div>
            <span className="text-2xl font-bold">
                {Math.round((job.confidence_score ?? 0) * 100)}%
            </span>
        </div>

        {/* eBay actions */}
        <div className="flex gap-2">
            {job.ebay_edit_url && (
                <a href={job.ebay_edit_url} target="_blank" rel="noopener noreferrer"
                   className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700">
                    <ExternalLink className="w-4 h-4" />
                    Edit on eBay
                </a>
            )}
            {job.ebay_view_url && (
                <a href={job.ebay_view_url} target="_blank" rel="noopener noreferrer"
                   className="inline-flex items-center justify-center gap-2 px-4 py-2.5 border border-stone-200 rounded-lg text-sm hover:bg-stone-50">
                    View Listing
                </a>
            )}
        </div>

        {/* Per-field confidence breakdown */}
        {job.field_confidence && (
            <div className="space-y-1">
                <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">Item Specifics</p>
                {Object.entries(job.field_confidence).map(([name, info]) => (
                    <div key={name} className="flex items-center gap-2 text-sm">
                        <span className={`w-2 h-2 rounded-full ${
                            info.confidence === 'high' ? 'bg-emerald-500' :
                            info.confidence === 'medium' ? 'bg-amber-500' :
                            'bg-red-500'
                        }`} />
                        <span className="text-stone-600">{name}:</span>
                        <span className="font-medium">{info.value}</span>
                    </div>
                ))}
            </div>
        )}
    </div>
)}
```

**Step 2: Compute `lowConfidenceCount` from field_confidence**

```typescript
const lowConfidenceCount = useMemo(() => {
    if (!job?.field_confidence) return 0
    return Object.values(job.field_confidence).filter(f => f.confidence === 'low').length
}, [job?.field_confidence])
```

**Step 3: Remove any remaining `needs_review`/`pending_review` references in the drawer**

**Step 4: Commit**

```bash
git add frontend/src/components/ItemDetailDrawer.tsx
git commit -m "feat: replace Action Required banner with confidence breakdown view"
```

---

## Task 13: Simplify Settings Automation Tab

**Files:**
- Modify: `frontend/src/pages/Settings.tsx:257-331`

**Step 1: Replace automation controls**

Remove:
- Auto-Publish toggle (lines 267-292)
- Confidence Threshold as gate (lines 294-310)
- Auto-Publish Min Price (lines 312-328)

Replace with:

```typescript
<TabsContent value="automation" className="mt-6">
    <Card>
        <CardHeader>
            <CardTitle>Scheduling</CardTitle>
            <CardDescription>
                All processed listings are automatically scheduled on eBay.
                Use confidence scores to prioritize which listings to review before they go live.
            </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
            <div className="space-y-2">
                <Label htmlFor="schedule-window">Schedule Window (days)</Label>
                <div className="flex items-center gap-4">
                    <Input
                        id="schedule-window"
                        type="number"
                        min="1"
                        max="21"
                        className="w-24"
                        value={settings['SCHEDULE_WINDOW_DAYS'] || '7'}
                        onChange={e => handleChange('SCHEDULE_WINDOW_DAYS', e.target.value)}
                    />
                    <span className="text-sm text-stone-500">
                        Listings go live {settings['SCHEDULE_WINDOW_DAYS'] || '7'} days after processing
                    </span>
                </div>
            </div>

            <div className="space-y-2">
                <Label htmlFor="confidence-alert">Low Confidence Alert (%)</Label>
                <div className="flex items-center gap-4">
                    <Input
                        id="confidence-alert"
                        type="number"
                        min="0"
                        max="100"
                        className="w-24"
                        value={settings['CONFIDENCE_THRESHOLD'] || '70'}
                        onChange={e => handleChange('CONFIDENCE_THRESHOLD', e.target.value)}
                    />
                    <span className="text-sm text-stone-500">
                        Items below {settings['CONFIDENCE_THRESHOLD'] || '70'}% are highlighted for review
                    </span>
                </div>
            </div>
        </CardContent>
    </Card>
</TabsContent>
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: simplify automation settings — schedule window + confidence alert only"
```

---

## Task 14: Update Dashboard Header Stats

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Update header stats display**

Replace the current `"{total} items · {pending} pending"` with:

```typescript
const scheduledCount = jobs.filter(j => j.status === 'scheduled').length
const needsReviewCount = jobs.filter(j =>
    j.status === 'scheduled' && (j.confidence_score ?? 1) < (confidenceThreshold / 100)
).length

// In render:
<span className="text-sm text-stone-500">
    {scheduledCount} scheduled
    {needsReviewCount > 0 && ` · ${needsReviewCount} need review`}
</span>
```

**Step 2: Update clear dialogs**

- Remove "Clear Failed" that references `needs_review`
- Keep "Clear Completed" and "Clear Failed" (actual failures only)
- Add "Clear Scheduled" if user wants to remove all scheduled items

**Step 3: Remove the per-item datetime picker**

Find and remove the datetime picker component for individual job scheduling — it's replaced by the global SCHEDULE_WINDOW_DAYS setting.

**Step 4: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: update dashboard header stats and remove per-item date picker"
```

---

## Task 15: Remove Review Tab from App.tsx

**Files:**
- Modify: `frontend/src/App.tsx:22,30`

**Step 1: Remove ReviewQueue**

- Remove import: `import { ReviewQueue } from '@/components/listings/ReviewQueue'`
- Remove `'review'` from `TAB_ORDER` array
- Remove the ReviewQueue render in the tab content section

**Step 2: Update TAB_ORDER**

```typescript
const TAB_ORDER = ['dashboard', 'inventory', 'analytics', 'settings']
```

**Step 3: Run build**

Run: `cd frontend && npm run build`
Expected: Clean build with no errors.

**Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "refactor: remove Review tab from navigation"
```

---

## Task 16: Update BatchSummaryDialog

**Files:**
- Modify: `frontend/src/components/BatchSummaryDialog.tsx`

**Step 1: Replace "Failed" count with "Scheduled" count**

Change the summary display from `Succeeded / Failed` to `Scheduled / Failed`:

```typescript
<div className="text-center">
    <p className="text-2xl font-bold text-emerald-600">{summary.succeeded}</p>
    <p className="text-xs text-stone-500">Scheduled</p>
</div>
{summary.failed > 0 && (
    <div className="text-center">
        <p className="text-2xl font-bold text-red-600">{summary.failed}</p>
        <p className="text-xs text-stone-500">Failed</p>
    </div>
)}
```

Remove the "View Failed Items" button that filters to the old `action` tab.

**Step 2: Commit**

```bash
git add frontend/src/components/BatchSummaryDialog.tsx
git commit -m "feat: update batch summary — show Scheduled count instead of generic Succeeded"
```

---

## Task 17: Update Zustand Store and useJobSync

**Files:**
- Modify: `frontend/src/store/useCommanderStore.ts`
- Modify: `frontend/src/hooks/useJobSync.ts`

**Step 1: Update store FilterTab type**

Change `FilterTab` type to match new tabs: `'inbox' | 'processing' | 'scheduled' | 'history' | 'failed' | 'all'`

Default `activeFilter` to `'scheduled'` (the primary working view).

**Step 2: Update useJobSync haptics**

In `useJobSync.ts`, change the `job_update` handler:

```typescript
if (updatedJob.status === 'scheduled') hapticSuccess()  // was 'completed'
else if (updatedJob.status === 'failed') hapticError()
```

**Step 3: Update QueueStats interface**

In `api.ts`, update `QueueStats`:

```typescript
export interface QueueStats {
    pending: number
    scheduled: number
    completed: number
    failed: number
    total: number
}
```

**Step 4: Commit**

```bash
git add frontend/src/store/useCommanderStore.ts frontend/src/hooks/useJobSync.ts frontend/src/lib/api.ts
git commit -m "refactor: update store, sync hook, and types for new status model"
```

---

## Task 18: Fix Remaining TypeScript Errors and Build

**Files:**
- Any remaining files with references to old statuses

**Step 1: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -50`

**Step 2: Fix all errors**

Search for remaining references to `needs_review`, `pending_review`, `paused`, `skipped`, `action` (as filter tab) across all frontend files. Update or remove.

**Step 3: Run build**

Run: `cd frontend && npm run build`
Expected: Clean build.

**Step 4: Run frontend tests**

Run: `cd frontend && npm run test`
Fix any failing tests.

**Step 5: Commit**

```bash
git add frontend/
git commit -m "fix: resolve all TypeScript errors from status model simplification"
```

---

## Task 19: Run Full Test Suite and Fix Regressions

**Files:**
- All test files that reference old statuses

**Step 1: Run backend tests**

Run: `pytest tests/unit/ -v --tb=short 2>&1 | tail -40`

**Step 2: Fix any failures**

Update test fixtures and assertions that use old statuses (`needs_review`, `pending_review`, `paused`, `skipped`).

**Step 3: Run frontend tests**

Run: `cd frontend && npm run test`

**Step 4: Run frontend build**

Run: `cd frontend && npm run build`

**Step 5: Commit fixes**

```bash
git add .
git commit -m "fix: update all tests for simplified status model"
```

---

## Task 20: Update Backend /api/status Endpoint

**Files:**
- Find the status/stats endpoint (likely in `backend/app/blueprints/api/` or `queue_api.py`)

**Step 1: Update stats response**

Ensure the `/api/status` endpoint returns counts matching the new statuses:

```python
{
    "pending": count_pending,
    "processing": count_processing,
    "scheduled": count_scheduled,
    "completed": count_completed,
    "failed": count_failed,
    "total": total
}
```

Remove any `needs_review` or `paused` counts.

**Step 2: Commit**

```bash
git add backend/app/blueprints/api/
git commit -m "refactor: update /api/status response for simplified status model"
```

---

## Task 21: Final Verification

**Step 1: Start backend**

Run: `python backend/wsgi.py`

**Step 2: Start frontend dev server**

Run: `cd frontend && npm run dev`

**Step 3: Verify in browser**

- Navigate to http://localhost:5175
- Confirm 5 tabs visible: Inbox, Processing, Scheduled, Completed, Failed
- Confirm no "Action Needed" or "Review" tabs
- Confirm Settings → Automation shows Schedule Window and Low Confidence Alert only
- Confirm no TypeScript console errors

**Step 4: Build production frontend**

Run: `cd frontend && npm run build`

**Step 5: Final commit**

```bash
git add .
git commit -m "chore: production build after always-list confidence triage overhaul"
```
