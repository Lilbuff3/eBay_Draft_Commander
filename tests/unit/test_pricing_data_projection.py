"""build_pricing_data is the one projection behind both /api/job/<id>/details
and /api/listings/pending. If they drift, the Review queue and the item drawer
render different prices for the same job."""
from backend.app.blueprints.api.helpers import build_pricing_data


AI_DATA = {
    'pricing_comps': [{'title': f'c{i}', 'price': 10.0 + i} for i in range(7)],
    'pricing_median': 12.5,
    'pricing_range': [10.0, 16.0],
    'pricing_comp_count': 7,
    'pricing_reasoning': 'Keyword comps',
    'pricing_confidence': 'low',
    'pricing_confidence_reason': 'wide spread',
    'pricing_source': 'market_data_keyword',
    'research': {'market_price': {'low': 9}},
}


def test_projects_every_key_the_frontend_reads():
    out = build_pricing_data(AI_DATA, {'confidence_score': 0.8})
    assert out['median_price'] == 12.5
    assert out['price_range'] == [10.0, 16.0]
    assert out['comp_count'] == 7
    assert out['reasoning'] == 'Keyword comps'
    assert out['pricing_confidence'] == 'low'
    assert out['pricing_confidence_reason'] == 'wide spread'
    assert out['source'] == 'market_data_keyword'
    assert out['confidence'] == 0.8
    assert out['market_price'] == {'low': 9}
    assert out['price_source_label']  # display copy is derived, not stored


def test_caps_comps_at_five():
    assert len(build_pricing_data(AI_DATA)['comps']) == 5


def test_empty_ai_data_is_safe():
    out = build_pricing_data({})
    assert out['comps'] == []
    assert out['median_price'] is None
    assert out['source'] == ''
