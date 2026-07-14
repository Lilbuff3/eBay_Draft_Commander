from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from integrations.hermes.capture_to_dc import (
    build_item_folder, capture, send_whatsapp, cancel_last, collect_and_capture,
)

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
    post_resp = MagicMock(); post_resp.status_code = 200
    post_resp.json.return_value = {'success': True, 'job_id': 'j1', 'scheduled_time': '2026-12-25T02:00:00+00:00'}
    get_resp = MagicMock(); get_resp.status_code = 200
    get_resp.json.return_value = {'id': 'j1', 'status': 'scheduled', 'user_title': 'Cool Item', 'user_price': '42.00', 'scheduled_time': '2026-12-25T02:00:00+00:00'}
    with patch('integrations.hermes.capture_to_dc._health_ok', return_value=True), \
         patch('integrations.hermes.capture_to_dc.requests.post', return_value=post_resp), \
         patch('integrations.hermes.capture_to_dc.requests.get', return_value=get_resp) as mock_get:
        msg = capture([str(src)], api_base='http://x', captures_dir=str(captures), poll_interval=0, poll_timeout=5)
    assert 'Scheduled' in msg
    assert 'Cool Item' in msg
    assert '$42.00' in msg
    # poll must hit the real details route (regression guard for the wrong-URL 404 bug)
    assert any('/api/job/j1/details' in str(c.args[0]) for c in mock_get.call_args_list)

def test_capture_timeout_reports_pending_not_scheduled(tmp_path):
    src = tmp_path / "a.png"; _png(src)
    captures = tmp_path / "captures"; captures.mkdir()
    post_resp = MagicMock(); post_resp.status_code = 200
    post_resp.json.return_value = {'success': True, 'job_id': 'j2', 'scheduled_time': '2026-12-25T02:00:00+00:00'}
    get_resp = MagicMock(); get_resp.status_code = 200
    get_resp.json.return_value = {'id': 'j2', 'status': 'processing'}  # never reaches a terminal status
    with patch('integrations.hermes.capture_to_dc._health_ok', return_value=True), \
         patch('integrations.hermes.capture_to_dc.requests.post', return_value=post_resp), \
         patch('integrations.hermes.capture_to_dc.requests.get', return_value=get_resp):
        msg = capture([str(src)], api_base='http://x', captures_dir=str(captures), poll_interval=0, poll_timeout=0.05)
    assert 'still analyzing' in msg.lower()
    assert 'Scheduled:' not in msg  # must NOT claim a finished listing on timeout

def test_capture_reports_offline_when_health_fails(tmp_path):
    captures = tmp_path / "captures"; captures.mkdir()
    with patch('integrations.hermes.capture_to_dc._health_ok', return_value=False):
        msg = capture(['x.png'], api_base='http://x', captures_dir=str(captures))
    assert 'offline' in msg.lower()

def test_capture_writes_last_job(tmp_path):
    src = tmp_path / "a.png"; _png(src)
    captures = tmp_path / "captures"; captures.mkdir()
    post_resp = MagicMock(); post_resp.status_code = 200
    post_resp.json.return_value = {'success': True, 'job_id': 'jX', 'scheduled_time': '2026-12-25T02:00:00+00:00'}
    get_resp = MagicMock(); get_resp.status_code = 200
    get_resp.json.return_value = {'id': 'jX', 'status': 'scheduled', 'user_title': 'T', 'user_price': '1', 'scheduled_time': '2026-12-25T02:00:00+00:00'}
    with patch('integrations.hermes.capture_to_dc._health_ok', return_value=True), \
         patch('integrations.hermes.capture_to_dc.requests.post', return_value=post_resp), \
         patch('integrations.hermes.capture_to_dc.requests.get', return_value=get_resp):
        capture([str(src)], api_base='http://x', captures_dir=str(captures), poll_interval=0, poll_timeout=5)
    assert (captures / '.last_job').read_text(encoding='utf-8') == 'jX'

def test_cancel_last_posts_cancel(tmp_path):
    captures = tmp_path / "captures"; captures.mkdir()
    (captures / '.last_job').write_text('jZ', encoding='utf-8')
    resp = MagicMock(); resp.status_code = 200; resp.json.return_value = {'success': True}
    with patch('integrations.hermes.capture_to_dc.requests.post', return_value=resp) as mock_post:
        msg = cancel_last(api_base='http://x', captures_dir=str(captures))
    assert msg == 'Cancelled jZ.'
    assert any('/api/jobs/jZ/cancel' in str(c.args[0]) for c in mock_post.call_args_list)
    assert not (captures / '.last_job').exists()  # marker cleared after a successful cancel

def test_cancel_last_nothing_to_cancel(tmp_path):
    captures = tmp_path / "captures"; captures.mkdir()
    assert cancel_last(api_base='http://x', captures_dir=str(captures)) == 'Nothing to cancel.'

def test_send_whatsapp_posts_to_bridge():
    with patch('integrations.hermes.capture_to_dc.requests.post') as mock_post:
        send_whatsapp('hello there', 'chat@lid', bridge_port=3000)
    assert mock_post.called
    assert mock_post.call_args.kwargs['json'] == {'chatId': 'chat@lid', 'message': 'hello there'}
    assert '127.0.0.1:3000/send' in str(mock_post.call_args.args[0])


def _stage(pending, name, body):
    pending.mkdir(parents=True, exist_ok=True)
    (pending / name).write_text(body)


def test_collect_isolates_second_item_during_capture(tmp_path):
    """Regression: two items' photos must never merge into one listing.

    Models the real merge bug — a second 'sell' fires while the first item is still in
    its capture/poll window. The fix atomically claims item A's frames out of the shared
    buffer BEFORE the long capture, so B's frames (arriving mid-analysis) stay isolated
    and are captured on their own, not swept in or destroyed."""
    captures = tmp_path / "captures"; captures.mkdir()
    chat = "chat@lid"
    safe = "chat_lid"  # re.sub of non-alnum -> _
    pending = captures / ".pending" / safe
    # Item A: three frames staged and ready.
    for i in range(3):
        _stage(pending, f"a{i}.jpg", f"A{i}")

    recorded_a = {}

    def fake_capture_a(image_paths, **kwargs):
        recorded_a['paths'] = list(image_paths)
        # Item B arrives DURING A's analysis: plugin recreates the shared buffer.
        _stage(captures / ".pending" / safe, "b0.jpg", "B0")
        _stage(captures / ".pending" / safe, "b1.jpg", "B1")
        return "captured-A"

    with patch('integrations.hermes.capture_to_dc.capture', side_effect=fake_capture_a):
        msg_a = collect_and_capture(chat, api_base='http://x', captures_dir=str(captures), debounce=0)
    assert msg_a == "captured-A"
    # A captured exactly its own 3 frames — none of B's.
    names_a = [Path(p).name for p in recorded_a['paths']]
    assert sorted(names_a) == ['a0.jpg', 'a1.jpg', 'a2.jpg']

    recorded_b = {}

    def fake_capture_b(image_paths, **kwargs):
        recorded_b['paths'] = list(image_paths)
        return "captured-B"

    with patch('integrations.hermes.capture_to_dc.capture', side_effect=fake_capture_b):
        msg_b = collect_and_capture(chat, api_base='http://x', captures_dir=str(captures), debounce=0)
    assert msg_b == "captured-B"
    # B survived A's capture and is listed on its own — exactly its 2 frames.
    names_b = [Path(p).name for p in recorded_b['paths']]
    assert sorted(names_b) == ['b0.jpg', 'b1.jpg']

    # No private claim dirs leaked behind.
    assert list((captures / ".pending").glob(".claimed_*")) == []


def test_collect_no_photos_returns_message(tmp_path):
    captures = tmp_path / "captures"; captures.mkdir()
    msg = collect_and_capture("chat@lid", api_base='http://x', captures_dir=str(captures), debounce=0)
    assert msg == "No photos found to list."
