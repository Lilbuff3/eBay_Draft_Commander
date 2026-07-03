"""Tests for cover_service.fetch_book_cover: Open Library first, thumbnail
fallback, tiny-image rejection, and eBay-minimum upscaling."""

import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from backend.app.services import cover_service


def _img_bytes(w, h, fmt='JPEG'):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), 'white').save(buf, fmt)
    return buf.getvalue()


def _resp(status=200, content=b''):
    r = MagicMock()
    r.status_code = status
    r.content = content
    return r


ISBN = '9780201616224'
FALLBACK = 'https://books.google.com/thumb.jpg'


class TestFetchBookCover:
    def test_open_library_success(self, tmp_path):
        big = _img_bytes(600, 900)
        with patch.object(cover_service.requests, 'get', return_value=_resp(200, big)) as mock_get:
            path = cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path)
        assert path is not None and path.exists()
        assert 'openlibrary' in mock_get.call_args_list[0].args[0]
        img = Image.open(path)
        assert max(img.size) >= 500

    def test_ol_404_falls_back_to_thumbnail(self, tmp_path):
        big = _img_bytes(550, 800)
        responses = [_resp(404), _resp(200, big)]
        with patch.object(cover_service.requests, 'get', side_effect=responses) as mock_get:
            path = cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path)
        assert path is not None
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[1].args[0] == FALLBACK

    def test_tiny_gif_rejected_then_fallback(self, tmp_path):
        tiny = _img_bytes(1, 1, fmt='GIF')
        big = _img_bytes(700, 1000)
        with patch.object(cover_service.requests, 'get', side_effect=[_resp(200, tiny), _resp(200, big)]):
            path = cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path)
        assert path is not None
        assert max(Image.open(path).size) >= 500

    def test_small_thumbnail_upscaled_to_target(self, tmp_path):
        small = _img_bytes(128, 190)
        with patch.object(cover_service.requests, 'get', side_effect=[_resp(404), _resp(200, small)]):
            path = cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path)
        assert path is not None
        img = Image.open(path)
        assert max(img.size) == cover_service.UPSCALE_TARGET_PX

    def test_both_sources_fail(self, tmp_path):
        with patch.object(cover_service.requests, 'get', side_effect=[_resp(404), _resp(500)]):
            assert cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path) is None

    def test_oversize_body_rejected(self, tmp_path):
        huge = b'x' * (cover_service.MAX_BYTES + 1)
        with patch.object(cover_service.requests, 'get', side_effect=[_resp(200, huge), _resp(404)]):
            assert cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path) is None

    def test_no_sources(self, tmp_path):
        assert cover_service.fetch_book_cover(None, None, tmp_path) is None

    def test_network_error_falls_through(self, tmp_path):
        big = _img_bytes(600, 900)
        with patch.object(cover_service.requests, 'get',
                          side_effect=[ConnectionError('boom'), _resp(200, big)]):
            path = cover_service.fetch_book_cover(ISBN, FALLBACK, tmp_path)
        assert path is not None
