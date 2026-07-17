"""suggest_factor: derive ACTIVE_TO_SOLD_FACTOR from real sold outcomes.

Synthetic scored rows only — no HTTP, no engine. Row shape mirrors the
benchmark's scored list: (match_type, est_sold, raw_median, would_list, actual).
"""
import pytest

from tools.accuracy_benchmark import suggest_factor


def R(match='exact-ID', raw_median=100.0, actual=87.0):
    return (match, actual, raw_median, None, actual)


class TestSuggestFactor:
    def test_median_ratio_of_actual_over_raw_median(self):
        scored = [R(raw_median=100, actual=80),
                  R(raw_median=100, actual=90),
                  R(raw_median=100, actual=85),
                  R(raw_median=200, actual=170),
                  R(raw_median=50, actual=45)]
        got = suggest_factor(scored)
        assert got['suggested_factor'] == pytest.approx(0.85, abs=0.001)
        assert got['n'] == 5
        assert got['basis'] == 'exact-ID'

    def test_prefers_exact_id_rows(self):
        scored = ([R(raw_median=100, actual=90)] * 5
                  + [R(match='keyword', raw_median=100, actual=10)] * 10)
        got = suggest_factor(scored)
        assert got['basis'] == 'exact-ID'
        assert got['suggested_factor'] == pytest.approx(0.90, abs=0.001)

    def test_falls_back_to_all_rows_when_few_exact(self):
        scored = ([R(raw_median=100, actual=90)] * 2
                  + [R(match='keyword', raw_median=100, actual=80)] * 6)
        got = suggest_factor(scored)
        assert got['basis'] == 'all'
        assert got['n'] == 8

    def test_low_sample_flagged(self):
        scored = [R()] * 10
        assert suggest_factor(scored)['low_sample'] is True
        scored = [R()] * 30
        assert suggest_factor(scored)['low_sample'] is False

    def test_zero_or_missing_medians_excluded(self):
        scored = [R(raw_median=0, actual=50), R(raw_median=100, actual=87)]
        got = suggest_factor(scored)
        assert got['n'] == 1

    def test_empty_returns_none(self):
        assert suggest_factor([]) is None
        assert suggest_factor([R(raw_median=0)]) is None


class TestFactorSetting:
    def test_active_to_sold_factor_in_settings(self):
        from backend.app.core.settings_manager import SettingsManager
        assert SettingsManager.DEFAULTS.get('ACTIVE_TO_SOLD_FACTOR') == '0.87'
        assert 'ACTIVE_TO_SOLD_FACTOR' in SettingsManager.SETTING_CATEGORIES['Automation']
