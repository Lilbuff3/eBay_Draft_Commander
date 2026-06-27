"""Tests for the WhatsApp back-channel notify helpers (auto-decide + tell me)."""
from unittest.mock import MagicMock, patch

from backend.app.services.whatsapp_notify import (
    build_duplicate_message,
    build_price_message,
    get_whatsapp_origin,
    notify_whatsapp,
)


# --- get_whatsapp_origin ---------------------------------------------------

def test_origin_none_for_missing_or_web_jobs():
    assert get_whatsapp_origin(None) is None
    assert get_whatsapp_origin({}) is None
    assert get_whatsapp_origin({'origin': 'nope'}) is None          # not a dict
    assert get_whatsapp_origin({'origin': {'channel': 'web'}}) is None
    assert get_whatsapp_origin({'origin': {'channel': 'whatsapp'}}) is None  # no chat_id


def test_origin_returned_for_whatsapp_job():
    md = {'origin': {'channel': 'whatsapp', 'chat_id': '123@c.us', 'bridge_port': 3000}}
    origin = get_whatsapp_origin(md)
    assert origin and origin['chat_id'] == '123@c.us'


# --- notify_whatsapp -------------------------------------------------------

def test_notify_noops_without_origin_or_message():
    assert notify_whatsapp(None, 'hi') is False
    assert notify_whatsapp({'chat_id': ''}, 'hi') is False
    assert notify_whatsapp({'chat_id': 'x'}, '') is False


def test_notify_posts_to_bridge_send_endpoint():
    origin = {'chat_id': '123@c.us', 'bridge_port': 4321}
    with patch('backend.app.services.whatsapp_notify.requests.post') as post:
        post.return_value = MagicMock(status_code=200)
        ok = notify_whatsapp(origin, 'hello')
    assert ok is True
    url = post.call_args[0][0]
    payload = post.call_args.kwargs['json']
    assert url == 'http://127.0.0.1:4321/send'
    assert payload == {'chatId': '123@c.us', 'message': 'hello'}


def test_notify_defaults_bridge_port_3000():
    with patch('backend.app.services.whatsapp_notify.requests.post') as post:
        post.return_value = MagicMock(status_code=204)
        notify_whatsapp({'chat_id': 'x'}, 'hi')
    assert post.call_args[0][0] == 'http://127.0.0.1:3000/send'


def test_notify_never_raises_on_network_error():
    with patch('backend.app.services.whatsapp_notify.requests.post', side_effect=OSError('down')):
        assert notify_whatsapp({'chat_id': 'x'}, 'hi') is False


def test_notify_false_on_non_2xx():
    with patch('backend.app.services.whatsapp_notify.requests.post') as post:
        post.return_value = MagicMock(status_code=500)
        assert notify_whatsapp({'chat_id': 'x'}, 'hi') is False


# --- message builders ------------------------------------------------------

def test_duplicate_message_mentions_skip_and_label():
    msg = build_duplicate_message('Vintage Shears', '12345')
    assert 'Skipped' in msg and 'Vintage Shears' in msg and '12345' in msg


def test_price_message_formats_price_and_reason():
    msg = build_price_message('Rare Camera', 1091.99, 'Price $1091.99 exceeds review threshold')
    assert 'Rare Camera' in msg and '$1091.99' in msg and 'eBay app' in msg
