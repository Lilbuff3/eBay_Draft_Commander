"""Tests for the sourcing verdict math + GET /api/lookup/comps endpoint."""
import pytest
from unittest.mock import patch

from backend.app.core.constants import (
    ACTIVE_TO_SOLD_FACTOR,
    EBAY_FINAL_VALUE_FEE_RATE,
    EBAY_PAYMENT_PROCESSING_FEE,
)
from backend.app.services.sourcing import compute_verdict


def expected_net(median, ship_cost):
    est_sold = median * ACTIVE_TO_SOLD_FACTOR
    assumed_list = est_sold + ship_cost
    return assumed_list * (1 - EBAY_FINAL_VALUE_FEE_RATE) - EBAY_PAYMENT_PROCESSING_FEE - ship_cost


KNOBS = dict(min_profit=5.0, roi_multiple=3.0, ship_cost=5.0)


class TestComputeVerdict:
    def test_no_data_when_zero_comps(self):
        result = compute_verdict(None, 0, [], **KNOBS)
        assert result['verdict'] == 'NO_DATA'
        assert result['max_buy'] is None

    def test_no_data_when_median_zero(self):
        result = compute_verdict(0, 5, [0, 0], **KNOBS)
        assert result['verdict'] == 'NO_DATA'

    def test_buy_with_solid_comps(self):
        result = compute_verdict(28.50, 12, [18.0, 28.5, 42.0], **KNOBS)
        assert result['verdict'] == 'BUY'
        net = expected_net(28.50, 5.0)
        assert result['net_proceeds'] == pytest.approx(net, abs=0.01)
        # ROI cap binds before min-profit here (net/3 < net-5 when net > 7.5)
        assert result['max_buy'] == pytest.approx(net / 3.0, abs=0.01)
        assert result['est_sold_value'] == pytest.approx(28.50 * ACTIVE_TO_SOLD_FACTOR, abs=0.01)

    def test_thin_with_few_comps(self):
        result = compute_verdict(28.50, 2, [25.0, 32.0], **KNOBS)
        assert result['verdict'] == 'THIN'
        assert result['max_buy'] > 1.0

    def test_pass_when_worthless(self):
        # $3 median book: net ~ $1.30, min-profit rule goes negative -> floor 0 -> PASS
        result = compute_verdict(3.00, 10, [2.0, 3.0, 4.0], **KNOBS)
        assert result['verdict'] == 'PASS'
        assert result['max_buy'] == 0.0

    def test_pass_beats_thin_when_both_apply(self):
        result = compute_verdict(3.00, 2, [3.0], **KNOBS)
        assert result['verdict'] == 'PASS'

    def test_min_profit_binds_on_cheap_items(self):
        # Pick a median where net - min_profit < net / roi  (net < 7.5)
        median = 8.00
        net = expected_net(median, 5.0)
        assert net < 7.5  # sanity: this median exercises the min-profit branch
        result = compute_verdict(median, 8, [8.0], **KNOBS)
        assert result['max_buy'] == pytest.approx(max(0.0, net - 5.0), abs=0.01)

    def test_roi_multiple_zero_disables_roi_cap(self):
        result = compute_verdict(28.50, 8, [28.5], min_profit=5.0, roi_multiple=0, ship_cost=5.0)
        net = expected_net(28.50, 5.0)
        assert result['max_buy'] == pytest.approx(net - 5.0, abs=0.01)

    def test_price_range_ignores_junk_prices(self):
        result = compute_verdict(20.0, 5, [0, None, 15.0, 25.0], **KNOBS)
        assert result['price_range'] == {'low': 15.0, 'high': 25.0}

    def test_settings_fallback_used_when_args_omitted(self):
        with patch('backend.app.services.sourcing.get_sourcing_settings',
                   return_value={'min_profit': 0.0, 'roi_multiple': 0.0, 'ship_cost': 0.0}):
            result = compute_verdict(20.0, 6, [20.0])
        net = expected_net(20.0, 0.0)
        assert result['max_buy'] == pytest.approx(net, abs=0.01)

    def test_confidence_high_on_many_tight_isbn_comps(self):
        r = compute_verdict(28.50, 12, [26.0, 28.5, 32.0], id_type='isbn', **KNOBS)
        assert r['confidence'] == 'high'
        assert r['confidence_reason']

    def test_confidence_medium_on_few_comps(self):
        r = compute_verdict(28.50, 2, [27.0, 30.0], **KNOBS)
        assert r['confidence'] in ('medium', 'low')

    def test_confidence_low_on_wide_spread(self):
        r = compute_verdict(30.0, 8, [5.0, 60.0, 30.0], **KNOBS)
        assert r['confidence'] == 'low'
        assert 'spread' in r['confidence_reason']

    def test_no_data_confidence_none(self):
        r = compute_verdict(None, 0, [], **KNOBS)
        assert r['confidence'] is None


@pytest.fixture
def app(tmp_path):
    from backend.app import create_app
    from backend.app.services.queue_manager import QueueManager
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


FAKE_COMPS = [
    {"title": "The C Programming Language 2nd Ed", "price": 28.50, "currency": "USD",
     "condition": "Used - Good", "end_date": "Active", "url": "https://www.ebay.com/itm/1"},
    {"title": "C Programming Language Kernighan Ritchie", "price": 24.00, "currency": "USD",
     "condition": "Used - Very Good", "end_date": "Active", "url": "https://www.ebay.com/itm/2"},
    {"title": "The C Programming Language ANSI", "price": 35.00, "currency": "USD",
     "condition": "Used - Good", "end_date": "Active", "url": "https://www.ebay.com/itm/3"},
    {"title": "C Programming Language book", "price": 30.00, "currency": "USD",
     "condition": "Used - Acceptable", "end_date": "Active", "url": "https://www.ebay.com/itm/4"},
    {"title": "The C Programming Language", "price": 26.00, "currency": "USD",
     "condition": "Used - Good", "end_date": "Active", "url": "https://www.ebay.com/itm/5"},
    {"title": "C Programming Language hardcover", "price": 40.00, "currency": "USD",
     "condition": "Used - Good", "end_date": "Active", "url": "https://www.ebay.com/itm/6"},
]

FIXED_KNOBS = {'min_profit': 5.0, 'roi_multiple': 3.0, 'ship_cost': 5.0}


class TestLookupCompsEndpoint:
    @patch('backend.app.services.sourcing.get_sourcing_settings', return_value=FIXED_KNOBS)
    @patch('backend.app.services.pricing_engine.PricingEngine.search_sold_listings',
           return_value=FAKE_COMPS)
    def test_buy_response_shape(self, mock_search, mock_knobs, client):
        resp = client.get('/api/lookup/comps?gtin=9780131103627')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['gtin'] == '9780131103627'
        assert data['verdict'] == 'BUY'
        # 4 comps share our USED_GOOD grade -> engine prices from same-grade subset
        assert data['comp_count'] == 4
        assert 'same-grade' in data['reasoning']
        assert data['max_buy'] > 1.0
        assert data['would_list_at'] is not None
        assert data['price_range'] == {'low': 24.0, 'high': 40.0}
        assert len(data['comps']) == 5  # top 5 only
        assert data['id_type'] == 'isbn'
        assert data['confidence'] == 'high'
        assert data['confidence_reason']
        assert 'ebay.com/sch' in data['ebay_search_url']
        # condition default passed through to the comps search
        assert mock_search.call_args.kwargs.get('condition') == 'USED_GOOD'

    @patch('backend.app.services.sourcing.get_sourcing_settings', return_value=FIXED_KNOBS)
    @patch('backend.app.services.pricing_engine.PricingEngine.search_sold_listings',
           return_value=[])
    def test_no_comps_returns_no_data(self, mock_search, mock_knobs, client):
        resp = client.get('/api/lookup/comps?gtin=012345678905')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['verdict'] == 'NO_DATA'
        assert data['comp_count'] == 0
        assert data['comps'] == []
        assert data['ebay_search_url'].endswith('012345678905')

    def test_rejects_invalid_gtin(self, client):
        assert client.get('/api/lookup/comps?gtin=notabarcode').status_code == 400
        assert client.get('/api/lookup/comps?gtin=12345').status_code == 400
        assert client.get('/api/lookup/comps').status_code == 400

    @patch('backend.app.services.sourcing.get_sourcing_settings', return_value=FIXED_KNOBS)
    @patch('backend.app.services.pricing_engine.PricingEngine.search_sold_listings',
           return_value=FAKE_COMPS)
    def test_accepts_hyphenated_isbn_and_condition_param(self, mock_search, mock_knobs, client):
        resp = client.get('/api/lookup/comps?gtin=978-0-13-110362-7&condition=LIKE_NEW')
        assert resp.status_code == 200
        assert resp.get_json()['gtin'] == '9780131103627'
        assert mock_search.call_args.kwargs.get('condition') == 'LIKE_NEW'


# ---------------------------------------------------------------------------
# assess_confidence with match_quality (pipeline reuse)
# ---------------------------------------------------------------------------

class TestAssessConfidenceMatchQuality:
    def _prices_tight(self):
        return [50.0, 52.0, 54.0, 55.0, 58.0]

    def _prices_moderate(self):
        # spread 4x: not tight (<=3x), not loose (>6x)
        return [10.0, 18.0, 25.0, 32.0, 40.0]

    def test_default_none_preserves_existing_behavior(self):
        from backend.app.services.sourcing import assess_confidence
        level, reason = assess_confidence(5, self._prices_tight(), 'isbn')
        assert level == 'high'
        assert 'ISBN' in reason

    def test_model_gated_treated_as_identity_match(self):
        from backend.app.services.sourcing import assess_confidence
        # moderate spread + keyword would normally be 'medium'; model gate lifts it
        level, _ = assess_confidence(5, self._prices_moderate(), 'keyword',
                                     match_quality='model_gated')
        assert level == 'high'

    def test_keyword_moderate_spread_without_model_is_medium(self):
        from backend.app.services.sourcing import assess_confidence
        level, _ = assess_confidence(5, self._prices_moderate(), 'keyword')
        assert level == 'medium'

    def test_floor_fallback_capped_at_low(self):
        from backend.app.services.sourcing import assess_confidence
        # even many tight comps can't be trusted if they only survived the floor
        level, reason = assess_confidence(6, self._prices_tight(), 'keyword',
                                          match_quality='floor_fallback')
        assert level == 'low'
        assert reason
