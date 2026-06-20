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
