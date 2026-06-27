"""
Tests for the supervised restart endpoint (POST /api/system/restart).

The endpoint only restarts when running under the supervisor (run_service.py),
which sets DC_SUPERVISED=1. Supervised -> exit with code 42 (supervisor
relaunches). Unsupervised -> 409, no exit.

os._exit and time.sleep are patched, and the reboot thread is run synchronously,
so the test process is never actually killed.
"""
import pytest

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
import backend.app.blueprints.api.system_api as system_api


@pytest.fixture
def app(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app


def test_restart_unsupervised_returns_409(app, monkeypatch):
    monkeypatch.delenv('DC_SUPERVISED', raising=False)
    resp = app.test_client().post('/api/system/restart')
    assert resp.status_code == 409
    body = resp.get_json()
    assert body['success'] is False
    assert 'supervisor' in body['error'].lower()


def test_restart_supervised_exits_with_code_42(app, monkeypatch):
    monkeypatch.setenv('DC_SUPERVISED', '1')

    exited = {}
    monkeypatch.setattr(system_api.os, '_exit', lambda code: exited.setdefault('code', code))
    monkeypatch.setattr(system_api.time, 'sleep', lambda _s: None)

    # Run the reboot worker synchronously so os._exit (patched) is observed here.
    class _SyncThread:
        def __init__(self, target=None, **_kw):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(system_api.threading, 'Thread', _SyncThread)

    resp = app.test_client().post('/api/system/restart')

    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    assert exited['code'] == system_api.RESTART_EXIT_CODE == 42
