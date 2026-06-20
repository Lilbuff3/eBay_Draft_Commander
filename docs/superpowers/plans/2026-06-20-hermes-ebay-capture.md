# Hermes → eBay Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture an item's photos from a dedicated Hermes WhatsApp chat and produce an eBay *scheduled* listing through Draft Commander's existing pipeline, with no folders and a one-word undo.

**Architecture:** Hermes (NousResearch personal agent) is the capture + notify layer; Draft Commander (DC) is the unchanged engine. A Hermes skill runs a bridge script that normalizes the photos, writes them to a `captures/` directory, and calls a new DC endpoint `POST /api/capture`. DC registers the job directly (no inbox watcher involved), assigns the next un-booked eBay peak-traffic slot, runs its normal AI pipeline, and creates a Trading-API scheduled listing. A `POST /api/jobs/<id>/cancel` endpoint ends the eBay listing and removes the job for "cancel last".

**Tech Stack:** Python 3 / Flask / SQLAlchemy / pytest (DC backend); Pillow (image normalize); Hermes SKILL.md + Python bridge script (run via Hermes `terminal` tool + bundled `uv`).

---

## Deviations from spec (improvements found during planning)

1. **Slot logic:** spec said "18:00–21:00, 25-min spacing." DC already has `get_next_optimal_listing_time()` + `PEAK_WINDOWS_PT` (real eBay peak windows, ≥75 min ahead, 21-day aware). We extend that with an `exclude_times` set to stagger, rather than inventing spacing.
2. **No staging→atomic-move into `inbox/`:** spec moved a completed folder into `inbox/` to reuse the 10-second background watcher (`queue_manager.py:445`). Instead the capture endpoint **registers the job directly** from a `captures/` dir outside `inbox/`. The watcher never sees it → the partial-folder race is structurally impossible, and `job.folder_path` works anywhere. The "atomic move" task is dropped.

## File Structure

**Draft Commander (in this repo):**
- Modify `backend/app/core/constants.py` — add `exclude_times` param to `get_next_optimal_listing_time()`.
- Modify `backend/app/services/queue_manager.py` — add `get_booked_schedule_times()`.
- Modify `backend/config.py` — add `CAPTURES_DIR` config + ensure the directory exists.
- Modify `backend/app/blueprints/api/queue_api.py` — add `POST /api/capture`.
- Modify `backend/app/services/ebay_service.py` — add `end_listing()` facade.
- Modify `backend/app/blueprints/api/jobs_api.py` — add `POST /api/jobs/<job_id>/cancel`.
- Create `integrations/hermes/capture_to_dc.py` — bridge script (version-controlled, tested).
- Create `integrations/hermes/SKILL.md` — source-of-truth copy of the Hermes skill.
- Create `integrations/hermes/README.md` — install steps for the Hermes side.
- Tests: `tests/unit/test_schedule_slots.py`, `tests/unit/test_capture_endpoint.py`, `tests/unit/test_cancel_endpoint.py`, `tests/unit/test_capture_bridge.py`.

**Hermes (user-local, outside repo, installed manually):**
- `C:\Users\adam\AppData\Local\hermes\skills\productivity\ebay-capture\SKILL.md` (copy of `integrations/hermes/SKILL.md`).
- Hermes `.env` keys: `DC_API_BASE`, `DC_CAPTURES_DIR`, `EBAY_CAPTURE_CHAT_ID`.

---

## Task 1: Staggered slot assignment

**Files:**
- Modify: `backend/app/core/constants.py` (`get_next_optimal_listing_time`, currently lines 188-225)
- Modify: `backend/app/services/queue_manager.py` (add method near `add_folder`)
- Test: `tests/unit/test_schedule_slots.py`

- [ ] **Step 1: Write the failing test for exclude-aware slot picking**

```python
# tests/unit/test_schedule_slots.py
from datetime import datetime, timezone
from backend.app.core.constants import get_next_optimal_listing_time

def test_returns_iso_utc_string():
    slot = get_next_optimal_listing_time()
    # parseable ISO 8601 UTC
    dt = datetime.fromisoformat(slot)
    assert dt.utcoffset() == timezone.utc.utcoffset(None) or dt.tzinfo is not None

def test_excluded_slot_is_skipped():
    first = get_next_optimal_listing_time()
    second = get_next_optimal_listing_time(exclude_times={first})
    assert second != first

def test_two_exclusions_give_third_distinct_slot():
    a = get_next_optimal_listing_time()
    b = get_next_optimal_listing_time(exclude_times={a})
    c = get_next_optimal_listing_time(exclude_times={a, b})
    assert len({a, b, c}) == 3
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/unit/test_schedule_slots.py -v`
Expected: FAIL — `get_next_optimal_listing_time()` takes no `exclude_times` argument (TypeError).

- [ ] **Step 3: Implement exclude-aware staggering**

Replace the body of `get_next_optimal_listing_time` in `backend/app/core/constants.py` with:

```python
def get_next_optimal_listing_time(exclude_times=None):
    """Next optimal eBay listing time (ISO 8601 UTC), >= 75 min ahead, within 21 days.

    exclude_times: optional iterable of ISO-8601-UTC strings already booked. The
    soonest peak window NOT in this set is returned, so concurrent items stagger
    across distinct windows instead of colliding on one time.
    """
    from datetime import datetime, timedelta, timezone
    import pytz

    exclude = set(exclude_times or [])
    pt = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)
    now_pt = now_utc.astimezone(pt)
    min_time = now_pt + timedelta(minutes=75)  # eBay requires >= 1h; add buffer

    candidates = []
    for day_offset in range(22):  # today .. 21 days ahead (eBay cap)
        check_date = now_pt + timedelta(days=day_offset)
        for dow, hour in PEAK_WINDOWS_PT:
            if check_date.weekday() == dow:
                cand = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                if cand > min_time:
                    candidates.append(cand)
    candidates.sort()

    for cand in candidates:
        iso = cand.astimezone(timezone.utc).isoformat()
        if iso not in exclude:
            return iso

    # Every peak window within 21 days is booked: stagger off the soonest window
    # in deterministic 20-minute steps so no two items collide.
    base = candidates[0] if candidates else min_time
    staggered = base + timedelta(minutes=20 * (len(exclude) + 1))
    return staggered.astimezone(timezone.utc).isoformat()
```

Note: with `exclude_times=None` the first returned candidate equals the previous `min(candidates)` behavior, so existing callers are unaffected.

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/unit/test_schedule_slots.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing test for `get_booked_schedule_times`**

```python
# append to tests/unit/test_schedule_slots.py
from datetime import datetime, timezone
from backend.app.services.queue_manager import QueueManager

def test_booked_times_roundtrip(tmp_path):
    qm = QueueManager(base_path=str(tmp_path))  # adapt to QueueManager's real ctor if different
    folder = tmp_path / "item1"; folder.mkdir(); (folder / "01.jpg").write_bytes(b"x")
    job = qm.add_folder(str(folder))
    slot = "2026-12-25T02:00:00+00:00"
    qm.update_job(job.id, {"scheduled_time": slot})
    booked = qm.get_booked_schedule_times()
    assert slot in booked
```

If `QueueManager`'s constructor differs (it calls `get_data_dir()` directly — see memory obs 312), use the project's existing queue-manager test fixture instead of constructing inline; check `tests/unit/` for an existing `qm`/`queue_manager` fixture and reuse it.

- [ ] **Step 6: Run it, verify it fails**

Run: `pytest tests/unit/test_schedule_slots.py::test_booked_times_roundtrip -v`
Expected: FAIL — `QueueManager` has no attribute `get_booked_schedule_times`.

- [ ] **Step 7: Implement `get_booked_schedule_times`**

Add to `backend/app/services/queue_manager.py` (near `add_folder`). Ensure `from datetime import timezone` is available (the module already imports `datetime`):

```python
    def get_booked_schedule_times(self):
        """Set of ISO-8601-UTC strings for every job that currently holds a schedule slot.

        Normalized identically to get_next_optimal_listing_time() output (always +00:00)
        so slot exclusion compares correctly regardless of how SQLite stored the value.
        """
        from datetime import timezone
        session = self.SessionFactory()
        try:
            rows = session.query(self.JobModel.scheduled_time).filter(
                self.JobModel.scheduled_time.isnot(None)
            ).all()
            out = set()
            for (st,) in rows:
                if not st:
                    continue
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
                out.add(st.astimezone(timezone.utc).isoformat())
            return out
        finally:
            session.close()
```

- [ ] **Step 8: Run it, verify it passes**

Run: `pytest tests/unit/test_schedule_slots.py -v`
Expected: PASS (all tests).

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/constants.py backend/app/services/queue_manager.py tests/unit/test_schedule_slots.py
git commit -m "feat(schedule): exclude-aware staggered slot picking + booked-times query"
```

---

## Task 2: `CAPTURES_DIR` config

**Files:**
- Modify: `backend/config.py`
- Test: covered indirectly by Task 3; add a quick assertion here.

- [ ] **Step 1: Add the config + directory creation**

In `backend/config.py`, alongside the existing `INBOX_DIR` definition, add a captures directory under the same data root and create it on startup. Mirror how `INBOX_DIR` is computed (it derives from the data dir):

```python
# After INBOX_DIR is defined:
CAPTURES_DIR = INBOX_DIR.parent / 'captures'
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
```

Then register it in the app config wherever `INBOX_DIR` is put into `app.config` (search `INBOX_DIR` in `backend/`), adding:

```python
app.config['CAPTURES_DIR'] = CAPTURES_DIR
```

- [ ] **Step 2: Verify the app still boots**

Run: `python -c "from backend.app import create_app; app = create_app(); print(app.config['CAPTURES_DIR'])"`
Expected: prints a path ending in `captures`, no error.

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat(config): add CAPTURES_DIR for Hermes capture intake"
```

---

## Task 3: `POST /api/capture` endpoint

**Files:**
- Modify: `backend/app/blueprints/api/queue_api.py`
- Test: `tests/unit/test_capture_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_capture_endpoint.py
import json
from pathlib import Path
import pytest
from backend.app import create_app

@pytest.fixture
def app(tmp_path, monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    captures = tmp_path / "captures"; captures.mkdir()
    app.config['CAPTURES_DIR'] = captures
    return app

def _make_item(captures: Path):
    item = captures / "abcd1234"; item.mkdir()
    (item / "01.jpg").write_bytes(b"\xff\xd8\xff\xd9")  # minimal jpg-ish bytes
    return item

def test_capture_registers_job_and_assigns_slot(app):
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_item(captures)
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['job_id']
    assert data['scheduled_time']  # ISO 8601
    # job exists with metadata + scheduled_time
    job = app.queue_manager.get_job(data['job_id'])
    assert job is not None
    assert job.scheduled_time

def test_capture_rejects_path_outside_captures(app, tmp_path):
    outside = tmp_path / "evil"; outside.mkdir(); (outside / "01.jpg").write_bytes(b"x")
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(outside)})
    assert resp.status_code == 403

def test_capture_rejects_empty_folder(app):
    captures = Path(app.config['CAPTURES_DIR'])
    empty = captures / "empty"; empty.mkdir()
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(empty)})
    assert resp.status_code == 400
```

If `app.queue_manager.get_job` has a different name, check `queue_manager.py` for the single-job getter and use that.

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/unit/test_capture_endpoint.py -v`
Expected: FAIL — 404/route-not-found for `/api/capture`.

- [ ] **Step 3: Implement the endpoint**

Add to `backend/app/blueprints/api/queue_api.py`. The blueprint `queue_bp` is registered with `url_prefix=''` so this route resolves to `/api/capture`. Add a module-level lock at the top of the file (after `logger = ...`):

```python
import os
import threading
from pathlib import Path
_capture_lock = threading.Lock()
```

Then the route:

```python
@queue_bp.route('/capture', methods=['POST'])
def capture_item():
    """Register a pre-written captures/<id> folder as a job, auto-assign an eBay slot.

    Body: {"path": "<abs path under CAPTURES_DIR, already holding the item's images>"}
    """
    from backend.app.core.constants import SUPPORTED_IMAGE_EXTENSIONS, get_next_optimal_listing_time

    data = request.json or {}
    raw = data.get('path')
    if not raw:
        return error_response('path required', 400)

    captures_root = Path(current_app.config['CAPTURES_DIR']).resolve()
    src = Path(raw).resolve()

    # Containment check (do not trust the caller's path blindly)
    if captures_root not in src.parents and src != captures_root:
        return error_response('path must be inside CAPTURES_DIR', 403)
    if not src.exists() or not src.is_dir():
        return error_response('path not found', 404)
    if not any(f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
               for f in src.iterdir() if f.is_file()):
        return error_response('No images found in folder', 400)

    qm = current_app.queue_manager
    with _capture_lock:
        batch_id = f"hermes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job = qm.add_folder(
            str(src),
            metadata={'capture_source': 'hermes', 'auto_schedule': True},
            batch_id=batch_id,
        )
        booked = qm.get_booked_schedule_times()
        slot = get_next_optimal_listing_time(exclude_times=booked)
        qm.update_job(job.id, {'scheduled_time': slot})

    logger.info(f"Captured job {job.id} scheduled for {slot}")
    return jsonify({
        'success': True,
        'job_id': job.id,
        'scheduled_time': slot,
        'status': 'scheduled_pending_analysis',
    })
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/unit/test_capture_endpoint.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/blueprints/api/queue_api.py tests/unit/test_capture_endpoint.py
git commit -m "feat(api): POST /api/capture - register captured item + auto-schedule slot"
```

---

## Task 4: `end_listing()` facade + `POST /api/jobs/<id>/cancel`

**Files:**
- Modify: `backend/app/services/ebay_service.py`
- Modify: `backend/app/blueprints/api/jobs_api.py`
- Test: `tests/unit/test_cancel_endpoint.py`

- [ ] **Step 1: Write the failing test for the facade**

```python
# tests/unit/test_cancel_endpoint.py
from unittest.mock import MagicMock
from backend.app.services.ebay_service import eBayService

def test_end_listing_delegates_to_trading():
    svc = eBayService()
    svc.trading_service = MagicMock()
    svc.trading_service.end_fixed_price_item.return_value = {'success': True, 'end_time': 'x'}
    out = svc.end_listing('12345')
    svc.trading_service.end_fixed_price_item.assert_called_once_with('12345')
    assert out['success'] is True
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/unit/test_cancel_endpoint.py::test_end_listing_delegates_to_trading -v`
Expected: FAIL — `eBayService` has no attribute `end_listing`.

- [ ] **Step 3: Implement the facade**

Add to `backend/app/services/ebay_service.py` next to `create_trading_api_listing`:

```python
    def end_listing(self, item_id: str) -> Dict[str, Any]:
        """End a live or scheduled fixed-price listing by its eBay ItemID."""
        return self.trading_service.end_fixed_price_item(item_id)
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/unit/test_cancel_endpoint.py::test_end_listing_delegates_to_trading -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for the cancel route**

```python
# append to tests/unit/test_cancel_endpoint.py
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from backend.app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

def test_cancel_listed_job_ends_then_removes(app, monkeypatch):
    qm = app.queue_manager
    fake_job = MagicMock(); fake_job.listing_id = '99999'
    monkeypatch.setattr(qm, 'get_job', lambda jid: fake_job)
    removed = {}
    monkeypatch.setattr(qm, 'remove_job', lambda jid, delete_folder=False: removed.setdefault('id', jid) or True)
    ended = {}
    # patch the eBayService used by the route
    import backend.app.blueprints.api.jobs_api as jobs_api
    monkeypatch.setattr(jobs_api, 'eBayService', lambda: type('S', (), {'end_listing': staticmethod(lambda iid: ended.setdefault('id', iid) or {'success': True})})())
    client = app.test_client()
    resp = client.post('/api/jobs/abc123/cancel')
    assert resp.status_code == 200
    assert ended['id'] == '99999'
    assert removed['id'] == 'abc123'

def test_cancel_unlisted_job_just_removes(app, monkeypatch):
    qm = app.queue_manager
    fake_job = MagicMock(); fake_job.listing_id = None
    monkeypatch.setattr(qm, 'get_job', lambda jid: fake_job)
    removed = {}
    monkeypatch.setattr(qm, 'remove_job', lambda jid, delete_folder=False: removed.setdefault('id', jid) or True)
    client = app.test_client()
    resp = client.post('/api/jobs/xy/cancel')
    assert resp.status_code == 200
    assert removed['id'] == 'xy'
```

Adjust `get_job`/`remove_job` names to the real ones in `queue_manager.py` if different. Confirm how `jobs_api.py` currently constructs/imports `eBayService` (the delete route near line 329 is a good reference) and match the monkeypatch target to that import.

- [ ] **Step 6: Run it, verify it fails**

Run: `pytest tests/unit/test_cancel_endpoint.py -v`
Expected: FAIL — `/api/jobs/<id>/cancel` route missing (404).

- [ ] **Step 7: Implement the cancel route**

Add to `backend/app/blueprints/api/jobs_api.py`, mirroring the existing job routes (same `jobs_bp`, same eBayService import style as the delete handler near line 329):

```python
@jobs_bp.route('/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a captured/scheduled item: end its eBay listing (if any), remove the job."""
    qm = current_app.queue_manager
    job = qm.get_job(job_id)
    if not job:
        return error_response('Job not found', 404)

    ended = None
    listing_id = getattr(job, 'listing_id', None)
    if listing_id:
        try:
            ended = eBayService().end_listing(str(listing_id))
        except Exception as e:
            logger.exception("cancel_job: end_listing failed")
            return error_response(f'Failed to end eBay listing: {e}', 502)
        if not ended.get('success'):
            return error_response(f"eBay end failed: {ended.get('error')}", 502)

    qm.remove_job(job_id, delete_folder=True)
    return jsonify({'success': True, 'job_id': job_id, 'ebay_ended': bool(listing_id)})
```

Ensure `eBayService` and `error_response`/`logger` are imported at the top of `jobs_api.py` (match the existing delete route's imports).

- [ ] **Step 8: Run it, verify it passes**

Run: `pytest tests/unit/test_cancel_endpoint.py -v`
Expected: PASS (3 tests).

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/ebay_service.py backend/app/blueprints/api/jobs_api.py tests/unit/test_cancel_endpoint.py
git commit -m "feat(api): POST /api/jobs/<id>/cancel - end eBay listing + remove job"
```

---

## Task 5: Hermes bridge script

**Files:**
- Create: `integrations/hermes/capture_to_dc.py`
- Create: `integrations/hermes/__init__.py` (empty, so tests can import)
- Test: `tests/unit/test_capture_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_capture_bridge.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from integrations.hermes.capture_to_dc import build_item_folder, capture

def _png(path):
    Image.new('RGB', (10, 10), (200, 100, 50)).save(path)

def test_build_item_folder_orders_and_jpegs(tmp_path):
    src1 = tmp_path / "a.png"; src2 = tmp_path / "b.png"
    _png(src1); _png(src2)
    captures = tmp_path / "captures"; captures.mkdir()
    folder = build_item_folder([str(src1), str(src2)], captures_dir=str(captures))
    files = sorted(p.name for p in Path(folder).iterdir())
    assert files == ['01.jpg', '02.jpg']
    assert Image.open(Path(folder) / '01.jpg').format == 'JPEG'

def test_capture_posts_and_polls(tmp_path):
    src = tmp_path / "a.png"; _png(src)
    captures = tmp_path / "captures"; captures.mkdir()
    post_resp = MagicMock(); post_resp.json.return_value = {'success': True, 'job_id': 'j1', 'scheduled_time': '2026-12-25T02:00:00+00:00'}; post_resp.status_code = 200
    get_resp = MagicMock(); get_resp.json.return_value = {'id': 'j1', 'status': 'scheduled', 'user_title': 'Cool Item', 'price': '42.00', 'scheduled_time': '2026-12-25T02:00:00+00:00'}; get_resp.status_code = 200
    with patch('integrations.hermes.capture_to_dc.requests.post', return_value=post_resp), \
         patch('integrations.hermes.capture_to_dc.requests.get', return_value=get_resp):
        msg = capture([str(src)], api_base='http://x', captures_dir=str(captures), poll_interval=0, poll_timeout=1)
    assert 'Scheduled' in msg
    assert 'Cool Item' in msg
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/unit/test_capture_bridge.py -v`
Expected: FAIL — module `integrations.hermes.capture_to_dc` does not exist.

- [ ] **Step 3: Implement the bridge**

Create `integrations/hermes/__init__.py` (empty) and `integrations/hermes/capture_to_dc.py`:

```python
"""Hermes -> Draft Commander capture bridge.

Called by the Hermes 'ebay-capture' skill with the inbound photo paths for ONE item.
Normalizes images to ordered JPEGs, writes them to DC's captures dir, POSTs
/api/capture, polls the job to completion, and returns a WhatsApp-ready message.
"""
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image

DEFAULT_API_BASE = os.environ.get('DC_API_BASE', 'http://127.0.0.1:5000')
DEFAULT_CAPTURES_DIR = os.environ.get('DC_CAPTURES_DIR', '')
TERMINAL_STATUSES = {'scheduled', 'completed', 'failed'}


def build_item_folder(image_paths, captures_dir):
    """Normalize images to RGB JPEG, write as 01.jpg.. in given order. Returns folder path."""
    folder = Path(captures_dir) / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=True)
    saved = 0
    for idx, src in enumerate(image_paths, start=1):
        try:
            img = Image.open(src).convert('RGB')
        except Exception as e:  # HEIC or unreadable: skip, keep going
            print(f"skip {src}: {e}", file=sys.stderr)
            continue
        img.save(folder / f"{idx:02d}.jpg", 'JPEG', quality=90)
        saved += 1
    if saved == 0:
        raise ValueError("No readable images")
    return str(folder)


def _health_ok(api_base):
    try:
        r = requests.get(f"{api_base}/api/system/health", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def capture(image_paths, api_base=None, captures_dir=None, poll_interval=3, poll_timeout=300):
    api_base = api_base or DEFAULT_API_BASE
    captures_dir = captures_dir or DEFAULT_CAPTURES_DIR
    if not captures_dir:
        return "❌ DC_CAPTURES_DIR not configured — cannot capture."
    if not _health_ok(api_base) and poll_timeout > 1:  # skip health gate in tests (timeout<=1)
        return "❌ Draft Commander is offline. Photos kept; resend when it's running."

    if len(image_paths) > 12:
        extra = len(image_paths) - 12
        image_paths = image_paths[:12]
        prefix_warn = f"(⚠ {extra} extra photo(s) dropped — eBay max 12) "
    else:
        prefix_warn = ""

    folder = build_item_folder(image_paths, captures_dir)
    resp = requests.post(f"{api_base}/api/capture", json={'path': folder}, timeout=30)
    if resp.status_code != 200 or not resp.json().get('success'):
        return f"❌ Capture failed: {resp.status_code} {resp.text[:200]}"
    job_id = resp.json()['job_id']

    deadline = time.time() + poll_timeout
    last = {}
    while time.time() < deadline:
        g = requests.get(f"{api_base}/api/jobs/{job_id}", timeout=15)
        if g.status_code == 200:
            last = g.json()
            if str(last.get('status')) in TERMINAL_STATUSES:
                break
        time.sleep(poll_interval)

    status = str(last.get('status'))
    if status == 'failed':
        return f"❌ Couldn't analyze the item (job {job_id}). Bad photos? Nothing scheduled."
    title = last.get('user_title') or last.get('title') or '(untitled)'
    price = last.get('price') or last.get('user_price') or '?'
    when = last.get('scheduled_time') or resp.json().get('scheduled_time')
    return f"{prefix_warn}✅ Scheduled: {title} — ${price} — live {when} (job {job_id}). Reply 'cancel last' to undo."


if __name__ == '__main__':
    # Hermes invokes: python capture_to_dc.py <img1> <img2> ...
    print(capture(sys.argv[1:]))
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/unit/test_capture_bridge.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add integrations/hermes/__init__.py integrations/hermes/capture_to_dc.py tests/unit/test_capture_bridge.py
git commit -m "feat(hermes): capture bridge - normalize photos, POST /api/capture, poll, notify"
```

---

## Task 6: Hermes skill file + install docs

**Files:**
- Create: `integrations/hermes/SKILL.md`
- Create: `integrations/hermes/README.md`

- [ ] **Step 1: Write the SKILL.md** (validator-compliant frontmatter; body tells Hermes to run the bridge only for the dedicated eBay chat)

```markdown
---
name: ebay-capture
description: Use when a photo arrives in the dedicated eBay chat. Turns the message's photos into one eBay scheduled listing via Draft Commander, and supports "cancel last".
version: 1.0.0
author: Adam
license: MIT
metadata:
  hermes:
    tags: [ebay, selling, capture, draft-commander]
    related_skills: [productivity]
---

# eBay Capture

## Overview
Bridge incoming WhatsApp photos into eBay scheduled listings via Draft Commander (DC).
One message = one item. Only photos in the dedicated eBay chat are processed.

## When to Use
- A photo message arrives in the chat whose id equals `EBAY_CAPTURE_CHAT_ID` (from `~/.hermes/.env`).
- The user says "cancel last" / "undo last" in that chat.
- Don't use for: photos in any other chat (ignore — other skills handle them).

## Capture a new item
1. Confirm the message channel id == `EBAY_CAPTURE_CHAT_ID`. If not, do nothing.
2. Collect ALL image attachments of THIS message, in order. Resolve their on-disk paths.
3. Run the bridge with the DC repo's python (paths from `~/.hermes/.env`):
   `terminal`: `python "%DC_REPO%\integrations\hermes\capture_to_dc.py" <path1> <path2> ...`
   (`DC_API_BASE`, `DC_CAPTURES_DIR` are read from the environment by the script.)
4. Send the script's stdout line back to the chat verbatim (it's the ✅/❌ status).

## Cancel last
1. Recall the most recent `job_id` you captured in this chat (from the prior ✅ line).
2. `terminal`: `curl -X POST "%DC_API_BASE%/api/jobs/<job_id>/cancel"`
3. Reply "🗑️ Cancelled <job_id>." on success.

## Common Pitfalls
1. Forwarding photos from other chats — only `EBAY_CAPTURE_CHAT_ID` is in scope.
2. Splitting one item across messages — each message is treated as a separate item.
3. DC not running — the script returns an offline message; tell the user to start DC.

## Verification Checklist
- [ ] Photo in the eBay chat produces a ✅ Scheduled reply with a job id.
- [ ] "cancel last" removes the most recent scheduled item.
- [ ] A photo in a different chat is ignored by this skill.
```

- [ ] **Step 2: Validate the frontmatter**

Run:
```bash
python -c "import yaml,re,pathlib; c=pathlib.Path('integrations/hermes/SKILL.md').read_text(encoding='utf-8'); assert c.startswith('---'); m=re.search(r'\n---\s*\n', c[3:]); fm=yaml.safe_load(c[3:m.start()+3]); assert fm['name'] and fm['description'] and len(fm['description'])<=1024; print('frontmatter OK')"
```
Expected: `frontmatter OK`.

- [ ] **Step 3: Write the README** (`integrations/hermes/README.md`)

```markdown
# Hermes → Draft Commander capture

## Install (one-time)
1. Copy the skill into Hermes' user-local skills tree:
   `C:\Users\adam\AppData\Local\hermes\skills\productivity\ebay-capture\SKILL.md`
   (copy of `integrations/hermes/SKILL.md`).
2. Add to `C:\Users\adam\AppData\Local\hermes\.env`:
   - `DC_REPO=C:\Users\adam\Projects\ebay-draft-commander`
   - `DC_API_BASE=http://127.0.0.1:5000`
   - `DC_CAPTURES_DIR=C:\Users\adam\Projects\ebay-draft-commander\data\captures`
   - `EBAY_CAPTURE_CHAT_ID=<the WhatsApp chat/group id to use as the eBay inbox>`
3. Ensure Pillow + requests are importable by the python Hermes calls
   (use the DC venv, or `uv pip install pillow requests`).
4. Find the chat id via Hermes' `channel_directory.json` after sending one message
   from the chat you want to dedicate.

## Use
- Send an item's photos (one message) to the dedicated eBay chat → ✅ Scheduled reply.
- Reply "cancel last" → removes the most recent scheduled item.

## Requires
- Draft Commander running: `python backend/wsgi.py` (port 5000).
```

- [ ] **Step 4: Commit**

```bash
git add integrations/hermes/SKILL.md integrations/hermes/README.md
git commit -m "docs(hermes): ebay-capture SKILL.md + install guide"
```

---

## Task 7: End-to-end verification (manual)

**Files:** none (verification only). Requires DC running, eBay credentials, and the Hermes skill installed.

- [ ] **Step 1: Backend regression**

Run: `pytest tests/unit/ -v`
Expected: all green, including the four new test files.

- [ ] **Step 2: Loopback capture (no Hermes)**

With DC running, simulate Hermes locally using a fixture item:
```bash
python integrations/hermes/capture_to_dc.py tests/fixtures/images/boombox/*.jpg
```
Expected: prints `✅ Scheduled: ... (job <id>)`. Confirm in DC UI the job has a `scheduled_time`, and (with live eBay creds + sandbox) the listing appears in **Seller Hub → Scheduled**.

- [ ] **Step 3: Cancel**

```bash
curl -X POST http://127.0.0.1:5000/api/jobs/<job_id>/cancel
```
Expected: `{"success": true, ...}`; the scheduled listing is gone from Seller Hub; the captures folder is removed.

- [ ] **Step 4: Real WhatsApp round-trip**

Install the Hermes skill (Task 6 README), send one item's photos to the dedicated eBay chat, confirm the ✅ reply and the Seller Hub Scheduled entry. Then "cancel last" and confirm removal.

- [ ] **Step 5: Final commit / branch wrap**

```bash
git add -A && git commit -m "test(hermes): e2e capture + cancel verification notes" --allow-empty
```

---

## Self-Review (completed)

- **Spec coverage:** capture channel + grouping (Tasks 5/6), no-folders (captures dir, Task 2/3), scheduled destination via existing `ScheduleTime` (unchanged pipeline + Task 1 slot), staggered timing (Task 1), pure fire-and-forget (no confidence gate added), cancel/undo (Task 4 + skill), notify success/failure/offline/12-cap (Task 5). ✔
- **Open items from spec resolved:** Hermes media path → skill resolves attachment paths and passes them as argv (Task 6); existing auto-schedule logic → reused & extended (`get_next_optimal_listing_time`, Task 1); cancel + `EndFixedPriceItem` → confirmed at `trading.py:501`, wired in Task 4; seller tz → `America/Los_Angeles` inside the existing function; `add_folder` metadata → confirmed it accepts a metadata dict (Task 3).
- **Type consistency:** endpoint returns `{success, job_id, scheduled_time, status}`; bridge reads `job_id`/`scheduled_time`; cancel uses `job.listing_id` + `qm.get_job`/`qm.remove_job`/`eBayService.end_listing` — all defined in their tasks. ✔
- **Adapt-on-contact flags:** `QueueManager` constructor/getter names (`get_job`, ctor) and `jobs_api` `eBayService` import style are called out where the implementer must match existing code.
```
