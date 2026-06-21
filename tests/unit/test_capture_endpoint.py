"""
Tests for POST /api/capture.

The Hermes WhatsApp bridge writes an item's images into a folder under
CAPTURES_DIR, then POSTs {"path": "<that folder>"}. The endpoint validates
the path is inside CAPTURES_DIR, registers a job directly from it (no file
move, no inbox watcher), and assigns a staggered eBay schedule slot.
"""
from pathlib import Path

import pytest

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager


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
