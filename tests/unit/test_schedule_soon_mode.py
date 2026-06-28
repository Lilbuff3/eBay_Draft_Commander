"""Tests for the LISTING_SCHEDULE_SOON_MINUTES override on scheduling."""
from datetime import datetime, timezone

from backend.app.core.constants import get_next_optimal_listing_time


def _minutes_from_now(iso):
    t = datetime.fromisoformat(iso)
    return (t - datetime.now(timezone.utc)).total_seconds() / 60


def test_soon_mode_schedules_near_future(monkeypatch):
    monkeypatch.setenv('LISTING_SCHEDULE_SOON_MINUTES', '90')
    assert 85 <= _minutes_from_now(get_next_optimal_listing_time()) <= 95


def test_soon_mode_clamps_below_ebay_floor(monkeypatch):
    monkeypatch.setenv('LISTING_SCHEDULE_SOON_MINUTES', '5')  # below eBay's ~1h min
    assert _minutes_from_now(get_next_optimal_listing_time()) >= 74  # clamped to 75


def test_soon_mode_staggers_concurrent_captures(monkeypatch):
    monkeypatch.setenv('LISTING_SCHEDULE_SOON_MINUTES', '75')
    first = get_next_optimal_listing_time()
    second = get_next_optimal_listing_time(exclude_times={first})
    assert first != second
    # second is staggered ~20 min after the first
    assert 18 <= (_minutes_from_now(second) - _minutes_from_now(first)) <= 22


def test_peak_windows_used_when_override_absent(monkeypatch):
    monkeypatch.delenv('LISTING_SCHEDULE_SOON_MINUTES', raising=False)
    t = datetime.fromisoformat(get_next_optimal_listing_time())
    assert t.minute == 0  # peak windows start on the hour; soon-mode rarely would
