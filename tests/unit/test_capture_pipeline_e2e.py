"""Offline end-to-end test for the Hermes capture -> eBay scheduled-listing wiring.

Every other test mocks at a single per-component boundary; this one drives the WHOLE
chain in one piece — real Flask app + real queue + real ProcessorService.create_listing
+ real scheduling logic — with only the external boundaries stubbed (Gemini analysis,
pricing, eBay taxonomy aspects, EPS image upload, and the Trading API call). No network,
no real listing, no Gemini quota.

The core assertion: the slot POST /api/capture assigned to a job is the slot that
reaches the listing-creation call — NOT a fresh "soonest" auto-schedule slot. To make
that meaningful we capture TWO items (the second gets a distinct, staggered slot) and
process the second: a broken pipeline that ignored job.scheduled_time would fall back to
get_next_optimal_listing_time() with no exclusions = the *first* (soonest) window, which
differs from the second item's captured slot.
"""
from pathlib import Path

import pytest
from PIL import Image

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
from backend.app.services.listing_ai_agent import ListingAIAgent
from backend.app.services.image_processor import ImageProcessor
from backend.app.services.processor_service import ProcessorService


@pytest.fixture
def app(tmp_path, monkeypatch):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    captures = tmp_path / "captures"
    captures.mkdir()
    app.config['CAPTURES_DIR'] = captures
    qm.set_app(app)
    # We drive _process_job synchronously; never let the real background worker run.
    monkeypatch.setattr(qm, 'start_processing', lambda: None)
    return app


def _make_item(captures: Path, name: str) -> Path:
    item = captures / name
    item.mkdir()
    Image.new('RGB', (8, 8), (120, 120, 120)).save(item / "01.jpg", "JPEG")
    return item


def _naive(iso: str) -> str:
    """Drop the timezone suffix — SQLite stores naive datetimes, so a slot read back
    from the DB loses the '+00:00' the slot picker emits."""
    return iso.split('+')[0].split('Z')[0]


def _stub_external_boundaries(monkeypatch, item: Path):
    """Stub only the external calls; the real pipeline orchestration still runs."""
    # Gemini vision analysis
    monkeypatch.setattr(
        ListingAIAgent, 'analyze_item',
        lambda self, job, imgs, condition, log=None: {
            'success': True,
            'title': 'Test Widget Model X',
            'raw_description': 'A test widget for the offline pipeline test.',
            'ai_suggested_price': '40.00',
            'category_id': '171485',
            'item_specifics': {'Brand': 'TestCo'},
            'confidence_score': 0.95,
            'ai_data': {
                'identification': {'brand': 'TestCo', 'model': 'X'},
                'image_paths': [str(item / '01.jpg')],
            },
        },
    )
    # Pricing (would otherwise hit the pricing engine / Gemini grounding)
    monkeypatch.setattr(
        ListingAIAgent, 'get_final_pricing',
        lambda self, *a, **k: {
            'price': '42.00', 'timing': {'total': 0.0},
            'comps': [], 'reasoning': '', 'source': 'test',
        },
    )
    # eBay taxonomy aspect fetch + resolver (network). Empty schema -> skipped.
    monkeypatch.setattr(
        ProcessorService, '_validate_and_enrich_specifics',
        lambda self, cat_id, specifics, _log=None: [],
    )
    # EPS image upload
    monkeypatch.setattr(
        ImageProcessor, 'upload_images',
        lambda self, folder, ordered_filenames=None, log_callback=None: {
            'urls': ['https://example.test/01.jpg'], 'timing': 0.0,
        },
    )


def test_captured_slot_reaches_trading_call(app, monkeypatch):
    captures = Path(app.config['CAPTURES_DIR'])
    item_a = _make_item(captures, "item_a")
    item_b = _make_item(captures, "item_b")

    # analyze_item/image paths point at item_b (the one we process); fine for both.
    _stub_external_boundaries(monkeypatch, item_b)

    # Capture the scheduled_time handed to the listing-creation call (the assertion point).
    seen = {}

    def fake_create_trading(self, **kwargs):
        seen['scheduled_time'] = kwargs.get('scheduled_time')
        return {
            'success': True, 'listing_id': 'TEST-123',
            'status': 'Scheduled' if kwargs.get('scheduled_time') else 'Active',
            'timing': 0.0,
        }

    monkeypatch.setattr(ProcessorService, '_create_trading_api_listing', fake_create_trading)

    client = app.test_client()

    # 1. Capture two items. The second gets a distinct, staggered slot.
    resp_a = client.post('/api/capture', json={'path': str(item_a)})
    resp_b = client.post('/api/capture', json={'path': str(item_b)})
    assert resp_a.status_code == 200, resp_a.get_data(as_text=True)
    assert resp_b.status_code == 200, resp_b.get_data(as_text=True)
    slot_a = resp_a.get_json()['scheduled_time']
    job_b_id = resp_b.get_json()['job_id']
    slot_b = resp_b.get_json()['scheduled_time']
    assert slot_a and slot_b
    assert slot_a != slot_b, "second capture should be staggered to a distinct slot"

    # 2. Drive the real pipeline synchronously on item B.
    qm = app.queue_manager
    qm.update_job(job_b_id, {'user_condition': 'USED_GOOD'})  # ensure a definite condition (no awaiting-condition gate)
    job_b = qm.get_job_by_id(job_b_id)
    with app.app_context():
        qm._process_job(job_b)

    # 3. The capture slot for B — not a fresh "soonest" slot — reached the listing call.
    assert seen.get('scheduled_time') == _naive(slot_b)
    assert seen['scheduled_time'] != _naive(slot_a)

    # 4. The job ends SCHEDULED with the listing id and its captured slot intact.
    final = qm.get_job_by_id(job_b_id)
    status = final.status.value if hasattr(final.status, 'value') else final.status
    assert status == 'scheduled'
    assert final.listing_id == 'TEST-123'
    assert _naive(str(final.scheduled_time)) == _naive(slot_b)

    # 5. Sanity: the app is still serving.
    assert client.get('/api/system/health').status_code == 200
