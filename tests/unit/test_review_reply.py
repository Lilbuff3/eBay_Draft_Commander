"""WhatsApp reply-to-review: backend side.

Reply "ok" -> approve at pre-filled price; a bare number -> set price and
approve; "skip" -> skip the job. Resolution: FIFO-oldest pending_review job
whose origin chat matches; the owner chat (WHATSAPP_NOTIFY_CHAT_ID) also
covers origin-less web jobs. Marker files under <captures>/.review_pending/
gate the Hermes plugin so normal chat text is never hijacked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.app.services.queue_job import JobStatus
from backend.app.services.review_reply import (
    parse_review_reply,
    resolve_pending_job,
    approve_job,
    apply_review_reply,
    append_review_marker,
    pop_review_marker,
    review_marker_path,
)


class TestParser:
    @pytest.mark.parametrize('text,expected', [
        ('ok', 'ok'), ('OK', 'ok'), (' Okay ', 'ok'), ('yes', 'ok'),
        ('approve', 'ok'),
        ('skip', 'skip'), ('SKIP', 'skip'),
        ('25', ('price', 25.0)), ('$12.50', ('price', 12.5)),
        ('7.99', ('price', 7.99)),
        ('hello', None), ('', None), (None, None),
        ('ok thanks', None), ('sell', None), ('cancel last', None),
        ('25 dollars', None), ('$', None),
    ])
    def test_matrix(self, text, expected):
        assert parse_review_reply(text) == expected


def _job(job_id, chat_id=None, created_at='2026-07-01T00:00:00',
         status=JobStatus.PENDING_REVIEW, title='Widget'):
    meta = {}
    if chat_id:
        meta['origin'] = {'channel': 'whatsapp', 'chat_id': chat_id,
                          'bridge_port': 3000}
    return SimpleNamespace(id=job_id, status=status, job_metadata=meta,
                           created_at=created_at, title=title,
                           user_title=None, price=None, user_price=None)


def _qm(jobs):
    qm = MagicMock()
    qm.get_all_jobs.return_value = jobs
    qm.get_job_by_id.side_effect = lambda jid: next(
        (j for j in jobs if j.id == jid), None)
    qm.update_job.return_value = True
    qm.is_processing.return_value = False
    qm.is_paused.return_value = False
    return qm


class TestResolve:
    def test_matches_origin_chat_fifo_oldest(self):
        jobs = [
            _job('b', chat_id='111', created_at='2026-07-02T00:00:00'),
            _job('a', chat_id='111', created_at='2026-07-01T00:00:00'),
            _job('c', chat_id='222', created_at='2026-06-30T00:00:00'),
        ]
        assert resolve_pending_job(_qm(jobs), '111', owner_chat_id='').id == 'a'

    def test_non_pending_jobs_ignored(self):
        jobs = [_job('a', chat_id='111', status=JobStatus.COMPLETED)]
        assert resolve_pending_job(_qm(jobs), '111', owner_chat_id='') is None

    def test_owner_chat_covers_originless_jobs(self):
        jobs = [_job('web1'), _job('wa1', chat_id='222')]
        got = resolve_pending_job(_qm(jobs), '999', owner_chat_id='999')
        assert got.id == 'web1'

    def test_non_owner_stranger_chat_matches_nothing(self):
        jobs = [_job('web1')]
        assert resolve_pending_job(_qm(jobs), '333', owner_chat_id='999') is None


class TestApprove:
    def test_approve_sets_flag_and_pending(self):
        jobs = [_job('a', chat_id='111')]
        qm = _qm(jobs)
        assert approve_job(qm, 'a') is True
        updates = qm.update_job.call_args.args[1]
        assert updates['status'] == JobStatus.PENDING
        assert updates['job_metadata']['user_approved'] is True
        assert 'user_price' not in updates

    def test_approve_with_price_sets_user_price(self):
        qm = _qm([_job('a', chat_id='111')])
        assert approve_job(qm, 'a', user_price=25.0) is True
        updates = qm.update_job.call_args.args[1]
        assert updates['user_price'] == 25.0

    def test_missing_job_returns_false(self):
        assert approve_job(_qm([]), 'nope') is False


class TestApplyReply:
    def test_ok_approves_and_reports_title(self, tmp_path):
        qm = _qm([_job('a', chat_id='111', title='Ross CPU Board')])
        result = apply_review_reply(qm, '111', 'ok', owner_chat_id='',
                                    captures_dir=str(tmp_path))
        assert result['success'] is True
        assert result['job_id'] == 'a'
        assert 'Ross CPU Board' in result['message']
        updates = qm.update_job.call_args.args[1]
        assert updates['job_metadata']['user_approved'] is True
        qm.start_processing.assert_called_once()

    def test_number_sets_price_then_approves(self, tmp_path):
        qm = _qm([_job('a', chat_id='111')])
        result = apply_review_reply(qm, '111', '$25', owner_chat_id='',
                                    captures_dir=str(tmp_path))
        assert result['success'] is True
        updates = qm.update_job.call_args.args[1]
        assert updates['user_price'] == 25.0
        assert '25.00' in result['message']

    def test_skip_marks_skipped(self, tmp_path):
        qm = _qm([_job('a', chat_id='111')])
        result = apply_review_reply(qm, '111', 'skip', owner_chat_id='',
                                    captures_dir=str(tmp_path))
        assert result['success'] is True
        updates = qm.update_job.call_args.args[1]
        assert updates['status'] == JobStatus.SKIPPED
        qm.start_processing.assert_not_called()

    def test_no_pending_job(self, tmp_path):
        result = apply_review_reply(_qm([]), '111', 'ok', owner_chat_id='',
                                    captures_dir=str(tmp_path))
        assert result['success'] is False
        assert 'no listing' in result['message'].lower()

    def test_unparsable_text(self, tmp_path):
        qm = _qm([_job('a', chat_id='111')])
        result = apply_review_reply(qm, '111', 'what is this', owner_chat_id='',
                                    captures_dir=str(tmp_path))
        assert result['success'] is False
        qm.update_job.assert_not_called()

    def test_marker_entry_popped_on_success(self, tmp_path):
        append_review_marker(str(tmp_path), '111', 'a')
        append_review_marker(str(tmp_path), '111', 'b')
        qm = _qm([_job('a', chat_id='111'), _job('b', chat_id='111')])
        apply_review_reply(qm, '111', 'ok', owner_chat_id='',
                           captures_dir=str(tmp_path))
        remaining = review_marker_path(str(tmp_path), '111').read_text().split()
        assert remaining == ['b']


class TestMarkers:
    def test_append_and_pop_fifo(self, tmp_path):
        append_review_marker(str(tmp_path), '111@c.us', 'j1')
        append_review_marker(str(tmp_path), '111@c.us', 'j2')
        marker = review_marker_path(str(tmp_path), '111@c.us')
        assert marker.exists()
        assert marker.read_text().split() == ['j1', 'j2']
        pop_review_marker(str(tmp_path), '111@c.us', 'j1')
        assert marker.read_text().split() == ['j2']

    def test_pop_last_entry_deletes_file(self, tmp_path):
        append_review_marker(str(tmp_path), '111', 'j1')
        pop_review_marker(str(tmp_path), '111', 'j1')
        assert not review_marker_path(str(tmp_path), '111').exists()

    def test_pop_missing_file_is_noop(self, tmp_path):
        pop_review_marker(str(tmp_path), 'ghost', 'j1')  # must not raise

    def test_chat_id_sanitized_for_filesystem(self, tmp_path):
        append_review_marker(str(tmp_path), '111@c.us/../evil', 'j1')
        path = review_marker_path(str(tmp_path), '111@c.us/../evil')
        assert path.parent.name == '.review_pending'
        assert '..' not in path.name and '/' not in path.name


class TestEndpoint:
    def _client(self, qm):
        from flask import Flask
        from backend.app.blueprints.api import api_bp
        app = Flask(__name__)
        app.config['CAPTURES_DIR'] = '/tmp/captures-nonexistent'
        app.register_blueprint(api_bp, url_prefix='/api')
        app.queue_manager = qm
        return app.test_client()

    def test_reply_endpoint_ok(self, monkeypatch):
        qm = _qm([_job('a', chat_id='111', title='Widget')])
        mock_settings = MagicMock()
        mock_settings.get.return_value = ''
        monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                            lambda: mock_settings)
        client = self._client(qm)
        resp = client.post('/api/review/reply',
                           json={'chat_id': '111', 'text': 'ok'})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_reply_endpoint_no_pending_404(self, monkeypatch):
        mock_settings = MagicMock()
        mock_settings.get.return_value = ''
        monkeypatch.setattr('backend.app.core.settings_manager.get_settings_manager',
                            lambda: mock_settings)
        client = self._client(_qm([]))
        resp = client.post('/api/review/reply',
                           json={'chat_id': '111', 'text': 'ok'})
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False
