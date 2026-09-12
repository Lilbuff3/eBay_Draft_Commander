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


def test_pending_listings_carry_the_name_fields_the_ui_reads(tmp_path):
    """/listings/pending returned raw to_dict(), which has folder_name but not
    name/display_name — so every Review row rendered a blank title and the
    inline edit form pre-filled empty."""
    from backend.app import create_app
    from backend.app.services.queue_manager import QueueManager
    from backend.app.services.queue_job import JobStatus

    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True

    folder = tmp_path / 'inbox' / 'canon-ae1'
    folder.mkdir(parents=True)
    (folder / 'photo_1.jpg').write_bytes(b'\xff\xd8')
    job = qm.add_folder(str(folder))
    qm.update_job(job.id, {
        'status': JobStatus.PENDING_REVIEW,
        'ai_data': {'listing': {'suggested_title': 'Canon AE-1 35mm SLR Body'}},
    })

    row = next(l for l in app.test_client().get('/api/listings/pending')
               .get_json()['listings'] if l['id'] == job.id)
    assert row['name'] == 'canon-ae1'
    assert row['display_name'] == 'Canon AE-1 35mm SLR Body'
