"""
Tests for exclude-aware optimal listing slot picking and booked-times lookup.

Part of the Hermes capture feature (Task 1): multiple items captured together
must stagger across DISTINCT eBay peak-traffic windows instead of all landing
on the same scheduled time.
"""
from backend.app.core.constants import get_next_optimal_listing_time
from backend.app.services.queue_manager import QueueManager


def test_returns_iso_utc_string():
    slot = get_next_optimal_listing_time()
    from datetime import datetime
    dt = datetime.fromisoformat(slot)
    assert dt.tzinfo is not None


def test_excluded_slot_is_skipped():
    first = get_next_optimal_listing_time()
    second = get_next_optimal_listing_time(exclude_times={first})
    assert second != first


def test_two_exclusions_give_third_distinct_slot():
    a = get_next_optimal_listing_time()
    b = get_next_optimal_listing_time(exclude_times={a})
    c = get_next_optimal_listing_time(exclude_times={a, b})
    assert len({a, b, c}) == 3


def test_booked_times_roundtrip(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    folder = tmp_path / "item1"
    folder.mkdir()
    (folder / "01.jpg").write_bytes(b"x")
    job = qm.add_folder(str(folder))
    slot = "2026-12-25T02:00:00+00:00"
    qm.update_job(job.id, {"scheduled_time": slot})
    booked = qm.get_booked_schedule_times()
    assert slot in booked
