"""
Tests for POST /api/capture.

The Hermes WhatsApp bridge writes an item's images into a folder under
CAPTURES_DIR, then POSTs {"path": "<that folder>"}. The endpoint validates
the path is inside CAPTURES_DIR, registers a job directly from it (no file
move, no inbox watcher), and assigns a staggered eBay schedule slot.

Also covers the photo-hash duplicate guardrail: a re-send of the same photos
within DUP_LOOKBACK_DAYS lands the new job in pending_review instead of
starting processing (see listing_guardrails.py).
"""
from pathlib import Path

import pytest
from PIL import Image

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
from backend.app.services.queue_job import JobStatus


@pytest.fixture
def app(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    captures = tmp_path / "captures"
    captures.mkdir()
    app.config['CAPTURES_DIR'] = captures
    return app


def _make_item(captures: Path):
    item = captures / "abcd1234"
    item.mkdir()
    (item / "01.jpg").write_bytes(b"\xff\xd8\xff\xd9")  # minimal jpg-ish bytes
    return item


def _make_real_photo_item(captures: Path, name: str, fill=(10, 20, 30)):
    """A capture folder with a real (Pillow-decodable) photo, for dedup tests."""
    item = captures / name
    item.mkdir()
    Image.new("RGB", (64, 64), color=fill).save(item / "01.jpg")
    return item


def _make_checker_photo_item(captures: Path, name: str, invert: bool = False):
    """A capture folder with a checkerboard photo -- dHash-distinguishable
    from a flat fill and from its own inverse, unlike two solid colors (which
    both hash to all-zero/all-one and collide)."""
    item = captures / name
    item.mkdir()
    img = Image.new("RGB", (64, 64))
    for x in range(64):
        for y in range(64):
            on = (x // 8 + y // 8) % 2 == 0
            if invert:
                on = not on
            shade = 240 if on else 10
            img.putpixel((x, y), (shade, shade, shade))
    img.save(item / "01.jpg")
    return item


def test_capture_registers_job_and_assigns_slot(app, monkeypatch):
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: None)
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_item(captures)
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['job_id']
    assert data['scheduled_time']
    assert data['scheduled'] is True
    job = app.queue_manager.get_job_by_id(data['job_id'])
    assert job is not None
    assert job.scheduled_time


def test_capture_rejects_path_outside_captures(app, tmp_path):
    outside = tmp_path / "evil"
    outside.mkdir()
    (outside / "01.jpg").write_bytes(b"x")
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(outside)})
    assert resp.status_code == 403


def test_capture_rejects_empty_folder(app):
    captures = Path(app.config['CAPTURES_DIR'])
    empty = captures / "empty"
    empty.mkdir()
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(empty)})
    assert resp.status_code == 400


def test_capture_rejects_missing_path_field(app):
    client = app.test_client()
    resp = client.post('/api/capture', json={})
    assert resp.status_code == 400


def test_capture_rejects_nonexistent_path(app):
    captures = Path(app.config['CAPTURES_DIR'])
    missing = captures / "does_not_exist"
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(missing)})
    assert resp.status_code == 404


def test_capture_two_items_get_distinct_slots(app, monkeypatch):
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: None)
    captures = Path(app.config['CAPTURES_DIR'])
    item1 = captures / "item1"
    item1.mkdir()
    (item1 / "01.jpg").write_bytes(b"x")
    item2 = captures / "item2"
    item2.mkdir()
    (item2 / "01.jpg").write_bytes(b"x")

    client = app.test_client()
    resp1 = client.post('/api/capture', json={'path': str(item1)})
    resp2 = client.post('/api/capture', json={'path': str(item2)})

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    slot1 = resp1.get_json()['scheduled_time']
    slot2 = resp2.get_json()['scheduled_time']
    assert slot1 != slot2


def test_capture_returns_500_if_add_folder_fails(app, monkeypatch):
    """Slot is now assigned atomically inside add_folder. If add_folder fails,
    no slotless job is left behind and the request surfaces a 500 via the
    blueprint error handler."""
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_item(captures)

    def _boom(*a, **k):
        raise RuntimeError('db write failed')

    monkeypatch.setattr(app.queue_manager, 'add_folder', _boom)
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['error'] == 'Internal server error'


def test_capture_starts_queue_when_idle(app, monkeypatch):
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_item(captures)
    monkeypatch.setattr(app.queue_manager, 'is_processing', lambda: False)
    monkeypatch.setattr(app.queue_manager, 'is_paused', lambda: False)
    started = {'n': 0}
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: started.__setitem__('n', started['n'] + 1))
    resp = app.test_client().post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 200
    assert started['n'] == 1


def test_capture_does_not_restart_when_busy(app, monkeypatch):
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_item(captures)
    monkeypatch.setattr(app.queue_manager, 'is_processing', lambda: True)
    started = {'n': 0}
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: started.__setitem__('n', started['n'] + 1))
    resp = app.test_client().post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 200
    assert started['n'] == 0


# ---------------------------------------------------------------------------
# Photo-hash duplicate guardrail
# ---------------------------------------------------------------------------

def test_capture_stores_photo_hashes_on_normal_capture(app, monkeypatch):
    """Non-duplicate capture proceeds as today, but now also stores
    job_metadata['photo_hashes'] for future dedup comparisons."""
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: None)
    captures = Path(app.config['CAPTURES_DIR'])
    item = _make_real_photo_item(captures, "first", fill=(10, 20, 30))
    client = app.test_client()
    resp = client.post('/api/capture', json={'path': str(item)})
    assert resp.status_code == 200
    data = resp.get_json()
    job = app.queue_manager.get_job_by_id(data['job_id'])
    assert job.job_metadata.get('photo_hashes')
    assert job.status != JobStatus.PENDING_REVIEW


def test_capture_flags_duplicate_photos_as_pending_review(app, monkeypatch):
    """Capturing the same photo twice (within DUP_LOOKBACK_DAYS) lands the
    second job in pending_review and does NOT start processing for it."""
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: None)
    captures = Path(app.config['CAPTURES_DIR'])
    client = app.test_client()

    item1 = _make_real_photo_item(captures, "original", fill=(50, 60, 70))
    resp1 = client.post('/api/capture', json={'path': str(item1)})
    assert resp1.status_code == 200
    job1_id = resp1.get_json()['job_id']

    # Re-send: identical photo content -> identical dHash -> duplicate.
    item2 = _make_real_photo_item(captures, "resend", fill=(50, 60, 70))
    started = {'n': 0}
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: started.__setitem__('n', started['n'] + 1))
    resp2 = client.post('/api/capture', json={'path': str(item2)})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    job2 = app.queue_manager.get_job_by_id(data2['job_id'])
    assert job2.status == JobStatus.PENDING_REVIEW
    assert job1_id in (job2.error_message or '')
    # Duplicate must not trigger processing.
    assert started['n'] == 0


def test_capture_different_photos_not_flagged_as_duplicate(app, monkeypatch):
    """Distinctly different photos never trip the duplicate guard, even back
    to back -- intentional variants/multiples stay safe."""
    monkeypatch.setattr(app.queue_manager, 'start_processing', lambda: None)
    captures = Path(app.config['CAPTURES_DIR'])
    client = app.test_client()

    item1 = _make_checker_photo_item(captures, "itemA", invert=False)
    resp1 = client.post('/api/capture', json={'path': str(item1)})
    assert resp1.status_code == 200

    item2 = _make_checker_photo_item(captures, "itemB", invert=True)
    resp2 = client.post('/api/capture', json={'path': str(item2)})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    job2 = app.queue_manager.get_job_by_id(data2['job_id'])
    assert job2.status != JobStatus.PENDING_REVIEW
    assert job2.job_metadata.get('photo_hashes')
