"""Markdown ladder math — pure, no eBay dependency."""
import pytest

from backend.app.services.markdown_engine import compute_markdown

KNOBS = dict(after_days=14, step_pct=5, floor_pct=70)


class TestComputeMarkdown:
    def test_not_due_before_after_days(self):
        assert compute_markdown(100, 100, 13, **KNOBS) is None

    def test_due_applies_one_step(self):
        assert compute_markdown(100, 100, 14, **KNOBS) == pytest.approx(95.0)

    def test_second_step_compounds_from_current(self):
        assert compute_markdown(100, 95.0, 30, **KNOBS) == pytest.approx(90.25)

    def test_step_clamped_to_floor(self):
        # 72 * 0.95 = 68.4 < floor 70 -> clamp to 70
        assert compute_markdown(100, 72.0, 60, **KNOBS) == pytest.approx(70.0)

    def test_at_floor_returns_none(self):
        assert compute_markdown(100, 70.0, 60, **KNOBS) is None

    def test_below_floor_returns_none(self):
        assert compute_markdown(100, 65.0, 60, **KNOBS) is None

    def test_aggressive_discovery_knobs(self):
        got = compute_markdown(125, 125, 7, after_days=7, step_pct=10, floor_pct=40)
        assert got == pytest.approx(112.50)

    def test_invalid_inputs_return_none(self):
        assert compute_markdown(0, 100, 30, **KNOBS) is None
        assert compute_markdown(100, 0, 30, **KNOBS) is None
        assert compute_markdown(None, 100, 30, **KNOBS) is None
        assert compute_markdown('abc', 100, 30, **KNOBS) is None
        assert compute_markdown(100, 100, 30, after_days=14, step_pct=0, floor_pct=70) is None

    def test_rounded_to_cents(self):
        got = compute_markdown(19.99, 19.99, 20, **KNOBS)
        assert got == round(got, 2)
