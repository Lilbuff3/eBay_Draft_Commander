from datetime import datetime, timezone
import pytest
import pytz
from unittest.mock import patch

from backend.app.core.constants import get_next_optimal_listing_time

def test_spring_forward_dst_transition():
    # In 2026, DST in America/Los_Angeles starts on Sunday, March 8, 2026 at 2:00 AM (Pacific Time).
    # Saturday, March 7, 2026 is PST (UTC-8). Sunday, March 8, 2026 is PDT (UTC-7).
    # Let's mock 'now' to be Saturday, March 7, 2026 at 12:00 PM UTC (4:00 AM PST).
    mocked_now = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
    
    with patch("datetime.datetime") as mock_datetime:
        # Mock datetime.now(timezone.utc) and datetime.now() behavior
        mock_datetime.now.return_value = mocked_now
        # Support isinstance(..., datetime) by keeping the original class
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        
        # Get the next optimal times
        first = get_next_optimal_listing_time()
        second = get_next_optimal_listing_time(exclude_times={first})
        
        # Verify first is Saturday, March 7, 2026 19:00 local time
        # In PST (UTC-8), Saturday 10:00 AM PT is 18:00 UTC. But mock_now is 12:00 UTC (4:00 AM PST),
        # so 10:00 AM PT is in the future.
        # Let's check candidate offsets:
        # Saturday March 7, 10:00 AM PT -> should be Saturday March 7, 18:00 UTC (offset -08:00)
        # Sunday March 8, 6:00 PM (18:00) PT -> should be Sunday March 8, 01:00 UTC Monday March 9 (offset -07:00)
        
        dt_first = datetime.fromisoformat(first)
        # Saturday March 7, 2026 10:00 AM PT is 18:00 UTC (since offset is -08:00)
        assert dt_first.strftime("%Y-%m-%d %H:%M") == "2026-03-07 18:00"

        # Let's look at a Sunday slot (which is March 8, 2026, after the 2:00 AM transition)
        # Sunday 6:00 PM PT (18:00) -> should be Monday, March 9, 2026 01:00 UTC (since offset is -07:00)
        pt = pytz.timezone('America/Los_Angeles')
        
        # Collect multiple slots to find one on Sunday/Monday
        slots = []
        exclude = set()
        for _ in range(10):
            slot = get_next_optimal_listing_time(exclude_times=exclude)
            slots.append(slot)
            exclude.add(slot)
            
        sunday_slot_utc = [s for s in slots if "2026-03-09T01:00:00" in s]
        assert len(sunday_slot_utc) > 0  # Verified Sunday 6:00 PM PT localized to 01:00 UTC Monday (correct PDT offset!)


def test_fall_back_dst_transition():
    # In 2026, DST in America/Los_Angeles ends on Sunday, November 1, 2026 at 2:00 AM (Pacific Time).
    # Saturday, Oct 31, 2026 is PDT (UTC-7). Sunday, Nov 1, 2026 is PST (UTC-8).
    # Mock 'now' to Saturday, Oct 31, 2026 at 12:00 PM UTC (5:00 AM PDT).
    mocked_now = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = mocked_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        
        slots = []
        exclude = set()
        for _ in range(10):
            slot = get_next_optimal_listing_time(exclude_times=exclude)
            slots.append(slot)
            exclude.add(slot)
            
        # Oct 31 (Saturday) 10:00 AM PT -> should be 17:00 UTC (PDT is -07:00)
        saturday_slot = [s for s in slots if "2026-10-31T17:00:00" in s]
        assert len(saturday_slot) > 0
        
        # Nov 1 (Sunday) 6:00 PM PT -> should be Nov 2 02:00 UTC (PST is -08:00)
        sunday_slot = [s for s in slots if "2026-11-02T02:00:00" in s]
        assert len(sunday_slot) > 0
