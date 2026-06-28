"""Tests for POST /api/jobs/<id>/retry — re-queue a job, incl. recovering a
job the duplicate guard skipped by mistake."""
import pytest

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
from backend.app.services.queue_job import JobStatus


@pytest.fixture
def app(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app


def _make_job(app, tmp_path, status):
    folder = tmp_path / "item1"
    folder.mkdir(exist_ok=True)
    (folder / "01.jpg").write_bytes(b"x")
    job = app.queue_manager.add_folder(str(folder))
    app.queue_manager.update_job(job.id, {"status": status})
    return job.id


def test_retry_skipped_job_requeues(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app.queue_manager, "start_processing", lambda: None)
    jid = _make_job(app, tmp_path, JobStatus.SKIPPED)
    resp = app.test_client().post(f"/api/jobs/{jid}/retry")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"
    assert app.queue_manager.get_job_by_id(jid).status == JobStatus.PENDING


def test_retry_starts_processing_when_idle(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app.queue_manager, "is_processing", lambda: False)
    monkeypatch.setattr(app.queue_manager, "is_paused", lambda: False)
    started = {"n": 0}
    monkeypatch.setattr(app.queue_manager, "start_processing",
                        lambda: started.__setitem__("n", started["n"] + 1))
    jid = _make_job(app, tmp_path, JobStatus.SKIPPED)
    assert app.test_client().post(f"/api/jobs/{jid}/retry").status_code == 200
    assert started["n"] == 1


def test_retry_unknown_job_404(app):
    assert app.test_client().post("/api/jobs/nope/retry").status_code == 404


def test_retry_completed_job_409(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app.queue_manager, "start_processing", lambda: None)
    jid = _make_job(app, tmp_path, JobStatus.COMPLETED)
    assert app.test_client().post(f"/api/jobs/{jid}/retry").status_code == 409
