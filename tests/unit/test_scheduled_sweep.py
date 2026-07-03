"""
Tests for QueueManager.finalize_past_due_scheduled().

Listings submitted with a future eBay ScheduleTime keep local status
'scheduled' after eBay publishes them. The sweep flips past-due scheduled
jobs that hold a listing_id to 'completed' (check-on-read from GET /api/jobs).
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.queue_manager import QueueManager, JobStatus


PAST = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
FUTURE = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()


@pytest.fixture
def qm(tmp_path):
    return QueueManager(base_path=tmp_path)


def make_job(qm, tmp_path, name, status, scheduled_time=None, listing_id=None):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "01.jpg").write_bytes(b"x")
    job = qm.add_folder(str(folder))
    updates = {"status": status}
    if scheduled_time:
        updates["scheduled_time"] = scheduled_time
    if listing_id:
        updates["listing_id"] = listing_id
    qm.update_job(job.id, updates)
    return job.id


def get_status(qm, job_id):
    job = qm.get_job_by_id(job_id)
    return job.status.value if hasattr(job.status, "value") else job.status


def test_past_due_with_listing_id_flips_to_completed(qm, tmp_path):
    job_id = make_job(qm, tmp_path, "past", JobStatus.SCHEDULED,
                      scheduled_time=PAST, listing_id="298000000001")
    before = qm.get_job_by_id(job_id).completed_at

    assert qm.finalize_past_due_scheduled() == 1
    assert get_status(qm, job_id) == "completed"
    # completed_at was stamped at processing time — sweep must not touch it
    assert qm.get_job_by_id(job_id).completed_at == before


def test_past_due_without_listing_id_untouched(qm, tmp_path):
    job_id = make_job(qm, tmp_path, "orphan", JobStatus.SCHEDULED,
                      scheduled_time=PAST)

    assert qm.finalize_past_due_scheduled() == 0
    assert get_status(qm, job_id) == "scheduled"


def test_future_scheduled_untouched(qm, tmp_path):
    job_id = make_job(qm, tmp_path, "future", JobStatus.SCHEDULED,
                      scheduled_time=FUTURE, listing_id="298000000002")

    assert qm.finalize_past_due_scheduled() == 0
    assert get_status(qm, job_id) == "scheduled"


def test_non_scheduled_statuses_untouched(qm, tmp_path):
    pending = make_job(qm, tmp_path, "pending", JobStatus.PENDING)
    failed = make_job(qm, tmp_path, "failed", JobStatus.FAILED,
                      scheduled_time=PAST, listing_id="298000000003")

    assert qm.finalize_past_due_scheduled() == 0
    assert get_status(qm, pending) == "pending"
    assert get_status(qm, failed) == "failed"


def test_sweep_is_idempotent(qm, tmp_path):
    make_job(qm, tmp_path, "past", JobStatus.SCHEDULED,
             scheduled_time=PAST, listing_id="298000000004")

    assert qm.finalize_past_due_scheduled() == 1
    assert qm.finalize_past_due_scheduled() == 0
