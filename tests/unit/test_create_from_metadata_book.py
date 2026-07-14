"""
Tests for the book-aware /api/jobs/create-from-metadata endpoint:
condition/price wiring, ai_data pre-seed (vision skip), user_approved,
optional multipart photo, and validation errors.
"""

import io
import json
import re
import pytest
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager


BOOK_PAYLOAD = {
    'title': 'The Pragmatic Programmer',
    'isbn': '9780201616224',
    'description': 'Classic software book.',
    'thumbnail': 'https://books.google.com/thumb.jpg',
    'condition': 'LIKE_NEW',
    'price': '24.99',
    'category_id': '267',
    'item_specifics': {'Author': 'Hunt', 'Book Title': 'The Pragmatic Programmer'},
    'pricing_data': {'suggested_price': 22.5},
    'user_approved': True,
    'source': 'batch_scan',
}


@pytest.fixture
def client_qm(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    app.config['INBOX_DIR'] = tmp_path / 'inbox'
    with app.test_client() as client:
        yield client, qm


def _post_book(client, overrides=None, no_cover=False):
    payload = {**BOOK_PAYLOAD, **(overrides or {})}
    cover = None if no_cover else Path('cover.jpg')
    with patch('backend.app.services.cover_service.fetch_book_cover', return_value=cover):
        return client.post('/api/jobs/create-from-metadata', json=payload)


class TestBookMetadataCreate:
    def test_creates_job_with_condition_and_price(self, client_qm):
        client, qm = client_qm
        resp = _post_book(client)
        data = resp.get_json()
        assert data['success'] is True

        job = qm.get_job_by_id(data['jobId'])
        # validate_condition canonicalizes LIKE_NEW -> USED_EXCELLENT
        assert job.user_condition == 'USED_EXCELLENT'
        assert float(job.user_price) == 24.99
        assert job.job_metadata['user_condition'] == 'USED_EXCELLENT'
        assert job.job_metadata['user_approved'] is True

    def test_preseeds_ai_data_for_batch_scan(self, client_qm):
        client, qm = client_qm
        resp = _post_book(client)
        job = qm.get_job_by_id(resp.get_json()['jobId'])

        ai = job.ai_data
        # 'listing' key present => listing_ai_agent skips Gemini vision
        assert ai['listing']['suggested_title'] == 'The Pragmatic Programmer'
        assert ai['listing']['suggested_price'] == 24.99
        assert ai['identification']['category_id'] == '267'
        assert ai['identification']['isbn'] == '9780201616224'
        assert ai['item_specifics']['Author'] == 'Hunt'
        assert ai['analysis_mode'] == 'book_metadata'

    def test_no_preseed_without_isbn(self, client_qm):
        client, qm = client_qm
        resp = _post_book(client, overrides={'isbn': ''})
        job = qm.get_job_by_id(resp.get_json()['jobId'])
        assert not (job.ai_data or {}).get('listing')

    def test_cover_flag_reflects_fetch_result(self, client_qm):
        client, _ = client_qm
        assert _post_book(client).get_json()['cover'] is True
        assert _post_book(client, no_cover=True).get_json()['cover'] is False

    def test_invalid_condition_rejected(self, client_qm):
        client, _ = client_qm
        resp = _post_book(client, overrides={'condition': 'MINTY_FRESH'})
        assert resp.status_code == 400

    def test_invalid_isbn_rejected(self, client_qm):
        client, _ = client_qm
        resp = _post_book(client, overrides={'isbn': '12345'})
        assert resp.status_code == 400

    def test_missing_title_rejected(self, client_qm):
        client, _ = client_qm
        resp = _post_book(client, overrides={'title': '  '})
        assert resp.status_code == 400

    def test_multipart_photo_saved_after_cover(self, client_qm, tmp_path):
        client, qm = client_qm
        photo = (io.BytesIO(b'\xff\xd8\xe0fakejpegdata'), 'shelf.jpg')
        with patch('backend.app.services.cover_service.fetch_book_cover', return_value=Path('cover.jpg')):
            resp = client.post(
                '/api/jobs/create-from-metadata',
                data={'payload': json.dumps(BOOK_PAYLOAD), 'photo': photo},
                content_type='multipart/form-data',
            )
        data = resp.get_json()
        assert data['success'] is True
        job = qm.get_job_by_id(data['jobId'])
        files = sorted(f.name for f in Path(job.folder_path).glob('*'))
        assert 'photo_1.jpg' in files
        # 'cover.jpg' sorts before 'photo_1.jpg' -> cover stays eBay picture #1
        assert files == sorted(files)

    def test_multipart_rejects_disallowed_file(self, client_qm):
        client, _ = client_qm
        evil = (io.BytesIO(b'MZ'), 'malware.exe')
        with patch('backend.app.services.cover_service.fetch_book_cover', return_value=None):
            resp = client.post(
                '/api/jobs/create-from-metadata',
                data={'payload': json.dumps(BOOK_PAYLOAD), 'photo': evil},
                content_type='multipart/form-data',
            )
        assert resp.status_code == 400

    def test_creates_get_distinct_collision_proof_folders(self, client_qm):
        """Two creates must never share a folder — the batch-path photo-merge guard.

        Folder name uses a full uuid so same-second requests can't collide on the
        suffix and silently merge two items' photos into one listing."""
        client, qm = client_qm
        j1 = qm.get_job_by_id(_post_book(client).get_json()['jobId'])
        j2 = qm.get_job_by_id(_post_book(client).get_json()['jobId'])
        assert j1.folder_path != j2.folder_path
        for job in (j1, j2):
            name = Path(job.folder_path).name
            assert re.fullmatch(r'metadata_import_\d+_[0-9a-f]{32}', name), name

    def test_plain_metadata_import_still_works(self, client_qm):
        """Non-book path (no isbn, no condition) unchanged."""
        client, qm = client_qm
        with patch('backend.app.services.cover_service.fetch_book_cover', return_value=None):
            resp = client.post('/api/jobs/create-from-metadata', json={
                'title': 'Some Random Item', 'source': 'metadata',
            })
        data = resp.get_json()
        assert data['success'] is True
        job = qm.get_job_by_id(data['jobId'])
        assert job.job_metadata['user_title'] == 'Some Random Item'
        assert not (job.ai_data or {}).get('listing')
