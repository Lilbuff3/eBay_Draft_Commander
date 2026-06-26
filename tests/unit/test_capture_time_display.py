"""WhatsApp capture confirmation should show Pacific time, not raw UTC.

7 PM PT peak windows serialize to 02:00 UTC, which read as "2 AM" in the chat
reply. _format_when_pt renders the UTC ISO timestamp in friendly US Pacific time.
"""
from integrations.hermes.capture_to_dc import _format_when_pt


class TestFormatWhenPT:
    def test_summer_utc_0200_is_7pm_pacific_prior_day(self):
        # 2026-07-01 02:00 UTC == 2026-06-30 19:00 PDT (UTC-7)
        out = _format_when_pt("2026-07-01T02:00:00+00:00")
        assert "7:00 PM PT" in out
        assert "Jun 30" in out

    def test_winter_utc_uses_pst_offset(self):
        # 2026-01-15 03:00 UTC == 2026-01-14 19:00 PST (UTC-8)
        out = _format_when_pt("2026-01-15T03:00:00+00:00")
        assert "7:00 PM PT" in out
        assert "Jan 14" in out

    def test_saturday_10am_window(self):
        # 2026-07-04 17:00 UTC == 2026-07-04 10:00 AM PDT (a real peak window)
        out = _format_when_pt("2026-07-04T17:00:00+00:00")
        assert "10:00 AM PT" in out

    def test_unparseable_returns_input_unchanged(self):
        assert _format_when_pt("not a date") == "not a date"

    def test_empty_or_none_returns_input(self):
        assert _format_when_pt("") == ""
        assert _format_when_pt(None) is None
