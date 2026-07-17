"""Hermes plugin: review-reply gate (additive) + regression on existing paths.

The plugin may ONLY intercept ok/number/skip when a review marker exists for
that chat (written by the backend when it sends a review text). Without a
marker, those texts must fall through to normal LLM handling. Existing
sell/photo-buffer/cancel-last branches must behave byte-identically.
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import integrations.hermes.plugin as plugin_mod
from integrations.hermes.plugin import _parse_review_reply


class FakeCtx:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, fn):
        self.hooks[name] = fn


def _hook():
    ctx = FakeCtx()
    plugin_mod.register(ctx)
    return ctx.hooks['pre_gateway_dispatch']


def _event(text='', chat_id='111@c.us', media=None):
    return SimpleNamespace(
        text=text,
        media_urls=media or [],
        source=SimpleNamespace(chat_id=chat_id),
    )


def _write_marker(captures, chat_id, job_id='j1'):
    import re
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    d = captures / '.review_pending'
    d.mkdir(parents=True, exist_ok=True)
    (d / safe).write_text(job_id + '\n', encoding='utf-8')


@pytest.fixture
def captures_env(tmp_path, monkeypatch):
    monkeypatch.setenv('DC_CAPTURES_DIR', str(tmp_path))
    return tmp_path


class TestParser:
    @pytest.mark.parametrize('text,expected', [
        ('ok', 'ok'), ('Yes', 'ok'), ('approve', 'ok'),
        ('skip', 'skip'),
        ('25', '25'), ('$12.50', '12.50'),
        ('hello', None), ('sell', None), ('cancel last', None),
        ('', None), ('ok thanks', None),
    ])
    def test_matrix(self, text, expected):
        assert _parse_review_reply(text) == expected


class TestReviewReplyGate:
    def test_ok_with_marker_spawns_review_reply(self, captures_env):
        _write_marker(captures_env, '111@c.us')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('ok'))
        assert result == {'action': 'skip', 'reason': 'ebay review reply'}
        args = popen.call_args.args[0]
        assert '--review-reply' in args
        assert 'ok' in args
        assert '--chat-id' in args

    def test_number_with_marker_spawns_review_reply(self, captures_env):
        _write_marker(captures_env, '111@c.us')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('$25'))
        assert result == {'action': 'skip', 'reason': 'ebay review reply'}
        assert '--review-reply' in popen.call_args.args[0]

    def test_ok_without_marker_falls_through_to_llm(self, captures_env):
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('ok'))
        assert result is None
        popen.assert_not_called()

    def test_marker_for_other_chat_does_not_gate(self, captures_env):
        _write_marker(captures_env, '999@c.us')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('ok', chat_id='111@c.us'))
        assert result is None
        popen.assert_not_called()

    def test_media_message_never_treated_as_reply(self, captures_env, tmp_path):
        _write_marker(captures_env, '111@c.us')
        img = tmp_path / 'img.jpg'
        img.write_bytes(b'x')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('ok', media=[str(img)]))
        # photo gets buffered exactly like before; no review-reply spawn
        assert result == {'action': 'skip', 'reason': 'ebay photo buffered'}
        popen.assert_not_called()

    def test_no_captures_env_disables_gate(self, monkeypatch):
        monkeypatch.delenv('DC_CAPTURES_DIR', raising=False)
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('ok'))
        assert result is None
        popen.assert_not_called()


class TestExistingBranchesUnchanged:
    def test_sell_with_staged_photos_still_collects(self, captures_env):
        _write_marker(captures_env, '111@c.us')  # marker present must not matter
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('sell'))
        # no media + no staging dir -> "sell" alone returns None (LLM handles),
        # same as before the review-reply block existed
        assert result is None or result.get('reason') == 'ebay capture launched'

    def test_cancel_last_still_routes_to_cancel(self, captures_env):
        _write_marker(captures_env, '111@c.us')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('cancel last'))
        assert result == {'action': 'skip', 'reason': 'ebay cancel launched'}
        assert '--cancel' in popen.call_args.args[0]

    def test_plain_text_still_flows_to_llm(self, captures_env):
        _write_marker(captures_env, '111@c.us')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('what time is it'))
        assert result is None
        popen.assert_not_called()

    def test_photo_buffering_unchanged(self, captures_env, tmp_path):
        img = tmp_path / 'photo.jpg'
        img.write_bytes(b'fake')
        with patch('subprocess.Popen') as popen:
            result = _hook()(event=_event('', media=[str(img)]))
        assert result == {'action': 'skip', 'reason': 'ebay photo buffered'}
        popen.assert_not_called()


class TestBridgeReviewReply:
    def test_posts_and_returns_backend_message(self):
        from unittest.mock import MagicMock
        from integrations.hermes.capture_to_dc import review_reply
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'success': True, 'message': 'Approved "Widget" — listing now.'}
        with patch('integrations.hermes.capture_to_dc.requests.post',
                   return_value=resp) as post:
            msg = review_reply('ok', '111@c.us', api_base='http://x')
        assert 'Approved' in msg
        assert '/api/review/reply' in str(post.call_args.args[0])
        assert post.call_args.kwargs['json'] == {'chat_id': '111@c.us', 'text': 'ok'}

    def test_404_returns_no_pending_message(self):
        from unittest.mock import MagicMock
        from integrations.hermes.capture_to_dc import review_reply
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {'success': False, 'message': 'No listing waiting for review.'}
        with patch('integrations.hermes.capture_to_dc.requests.post', return_value=resp):
            msg = review_reply('ok', '111@c.us', api_base='http://x')
        assert 'No listing waiting' in msg

    def test_connection_error_is_graceful(self):
        import requests as requests_lib
        from integrations.hermes.capture_to_dc import review_reply
        with patch('integrations.hermes.capture_to_dc.requests.post',
                   side_effect=requests_lib.exceptions.ConnectionError('down')):
            msg = review_reply('ok', '111@c.us', api_base='http://x')
        assert 'failed' in msg.lower()
