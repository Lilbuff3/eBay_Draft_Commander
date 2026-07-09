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


# --- get_notify_destination (owner-chat fallback for web jobs) --------------

def test_destination_prefers_whatsapp_origin():
    from backend.app.services.whatsapp_notify import get_notify_destination
    md = {'origin': {'channel': 'whatsapp', 'chat_id': '123@c.us', 'bridge_port': 3001}}
    dest = get_notify_destination(md)
    assert dest['chat_id'] == '123@c.us'
    assert dest['bridge_port'] == 3001


def test_destination_owner_fallback_from_settings():
    from backend.app.services.whatsapp_notify import get_notify_destination
    mgr = MagicMock()
    mgr.get.return_value = '555@c.us'
    with patch('backend.app.core.settings_manager.get_settings_manager', return_value=mgr):
        dest = get_notify_destination(None)
    assert dest['chat_id'] == '555@c.us'
    assert dest['bridge_port'] == 3000


def test_destination_none_when_setting_empty():
    from backend.app.services.whatsapp_notify import get_notify_destination
    mgr = MagicMock()
    mgr.get.return_value = ''
    with patch('backend.app.core.settings_manager.get_settings_manager', return_value=mgr):
        assert get_notify_destination(None) is None
        assert get_notify_destination({}) is None


# --- review + summary message builders --------------------------------------

def test_price_review_message_conflict_shows_both_prices():
    from backend.app.services.whatsapp_notify import build_price_review_message
    msg = build_price_review_message('Owlet Smart Sock 2', 99.99, 12.18, 99.99,
                                     'comps vs AI 8.2x apart')
    assert 'Owlet Smart Sock 2' in msg
    assert '$12.18' in msg and '$99.99' in msg
    assert 'review' in msg.lower()


def test_price_review_message_plain_low_confidence():
    from backend.app.services.whatsapp_notify import build_price_review_message
    msg = build_price_review_message('Widget', 20.0, None, None, 'only 2 comps')
    assert 'Widget' in msg and '$20.00' in msg and 'only 2 comps' in msg


def test_queue_summary_message_counts_and_value():
    from backend.app.services.whatsapp_notify import build_queue_summary_message
    msg = build_queue_summary_message(7, 412.50, 2)
    assert '7 listed' in msg and '$412.50' in msg and '2' in msg

    msg_no_review = build_queue_summary_message(3, 99.0, 0)
    assert 'review' not in msg_no_review.lower()
