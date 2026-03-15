"""
Tests for job details API endpoint field mapping.

Verifies that AI data with various field name conventions
is correctly normalized when served to the frontend.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager


def _make_mock_job(job_id, folder_path, ai_data=None, **overrides):
    """Create a mock job object."""
    job = MagicMock()
    job.id = job_id
    job.folder_path = str(folder_path)
    job.folder_name = Path(folder_path).name
    job.ai_data = ai_data or {}
    job.user_title = overrides.get('user_title', None)
    job.user_price = overrides.get('user_price', None)
    job.user_description = overrides.get('user_description', None)
    job.user_condition = overrides.get('user_condition', None)
    job.item_specifics = overrides.get('item_specifics', None)
    job.scheduled_time = overrides.get('scheduled_time', None)
    job.confidence_score = overrides.get('confidence_score', 0.9)
    job.price = overrides.get('price', None)
    job.timing = overrides.get('timing', None)
    job.job_metadata = overrides.get('job_metadata', None)
    job.status = overrides.get('status', 'pending_review')
    return job


@pytest.fixture
def app_client(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    return app, app.test_client(), qm


class TestGetItemAspectsParsing:
    """Bug: get_item_aspects reads aspectUsage/relevantAspectValues at top level,
    but eBay nests them inside aspectConstraint and uses aspectValues."""

    def test_aspects_parse_nested_constraint(self):
        """eBay returns aspectUsage inside aspectConstraint, values in aspectValues."""
        from backend.app.services.ebay.taxonomy import get_item_aspects

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            'aspects': [
                {
                    'localizedAspectName': 'Brand',
                    'aspectConstraint': {
                        'aspectDataType': 'STRING',
                        'aspectUsage': 'RECOMMENDED',
                        'aspectRequired': True,
                    },
                    'aspectValues': [
                        {'localizedValue': 'Sharpe'},
                        {'localizedValue': 'DeVilbiss'},
                    ]
                },
                {
                    'localizedAspectName': 'Type',
                    'aspectConstraint': {
                        'aspectDataType': 'STRING',
                        'aspectUsage': 'RECOMMENDED',
                        'aspectRequired': False,
                    },
                    'aspectValues': [
                        {'localizedValue': 'HVLP Sprayer'},
                        {'localizedValue': 'Conventional Sprayer'},
                    ]
                },
            ]
        }

        with patch('backend.app.services.ebay.taxonomy.requests.get', return_value=fake_response), \
             patch('backend.app.services.ebay.taxonomy._check_cache', return_value=None), \
             patch('backend.app.services.ebay.taxonomy._save_cache'), \
             patch('backend.app.services.ebay.taxonomy._get_headers', return_value={}):

            result = get_item_aspects('260160')

            # Required aspects should be identified
            assert len(result['required']) >= 1, "Brand (aspectRequired=true) should be in required"
            brand = next((a for a in result['required'] if a['name'] == 'Brand'), None)
            assert brand is not None, "Brand should be in required list"
            assert 'Sharpe' in brand['values'], "Brand values should include Sharpe"
            assert 'DeVilbiss' in brand['values'], "Brand values should include DeVilbiss"

            # Type (not required) should be in optional
            type_aspect = next((a for a in result['optional'] if a['name'] == 'Type'), None)
            assert type_aspect is not None, "Type should be in optional list"
            assert 'HVLP Sprayer' in type_aspect['values']


class TestJobDetailsDescriptionMapping:
    """Bug: AI returns listing.description_html but API only checks listing.description"""

    def test_description_html_is_returned(self, app_client, tmp_path):
        """When AI returns description_html, API should include it in ai_description."""
        app, client, qm = app_client

        # Create a real folder with an image
        job_folder = tmp_path / 'test_item'
        job_folder.mkdir()
        (job_folder / 'photo.jpg').write_bytes(b'\xff\xd8\xff\xe0fake')

        ai_data = {
            'listing': {
                'suggested_title': 'Sharpe 450 Spray Gun',
                'description_html': '<b>Brand:</b> Sharpe<br>Used spray gun in good condition.',
                'suggested_price': '80',
            },
            'seo_title': 'Sharpe Spray Gun Model 450',
        }

        mock_job = _make_mock_job('test123', str(job_folder), ai_data=ai_data)

        with app.app_context():
            with patch.object(qm, 'get_job_by_id', return_value=mock_job):
                response = client.get('/api/job/test123/details')
                data = json.loads(response.data)

                assert data['success'] is True
                assert data['ai_description'] != '', \
                    "ai_description should not be empty when description_html exists"
                assert 'Sharpe' in data['ai_description']

    def test_plain_description_still_works(self, app_client, tmp_path):
        """When AI returns plain description, it should still work."""
        app, client, qm = app_client

        job_folder = tmp_path / 'test_item2'
        job_folder.mkdir()
        (job_folder / 'photo.jpg').write_bytes(b'\xff\xd8\xff\xe0fake')

        ai_data = {
            'listing': {
                'suggested_title': 'Test Item',
                'description': 'A plain text description.',
                'suggested_price': '20',
            },
        }

        mock_job = _make_mock_job('test456', str(job_folder), ai_data=ai_data)

        with app.app_context():
            with patch.object(qm, 'get_job_by_id', return_value=mock_job):
                response = client.get('/api/job/test456/details')
                data = json.loads(response.data)

                assert data['ai_description'] == 'A plain text description.'


class TestJobDetailsSpecificsMerge:
    """Bug: Item specifics from AI exist but aren't reflected in aspect schema"""

    def test_item_specifics_values_populate_schema(self, app_client, tmp_path):
        """When AI returns item_specifics and ebay_aspect_schema,
        the schema should include current values from item_specifics."""
        app, client, qm = app_client

        job_folder = tmp_path / 'test_item3'
        job_folder.mkdir()
        (job_folder / 'photo.jpg').write_bytes(b'\xff\xd8\xff\xe0fake')

        ai_data = {
            'listing': {'suggested_title': 'Test Item'},
            'item_specifics': {
                'Brand': 'Sharpe',
                'Model': '450',
                'Type': 'Spray Gun Cup',
            },
            'ebay_aspect_schema': [
                {'name': 'Brand', 'usage': None, 'type': None, 'values': [], 'isRequired': False},
                {'name': 'Type', 'usage': None, 'type': None, 'values': [], 'isRequired': False},
                {'name': 'Model', 'usage': None, 'type': None, 'values': [], 'isRequired': False},
                {'name': 'Power Source', 'usage': None, 'type': None, 'values': [], 'isRequired': False},
            ],
        }

        mock_job = _make_mock_job('test789', str(job_folder), ai_data=ai_data,
                                  item_specifics={'Brand': 'Sharpe', 'Model': '450', 'Type': 'Spray Gun Cup'})

        with app.app_context():
            with patch.object(qm, 'get_job_by_id', return_value=mock_job):
                response = client.get('/api/job/test789/details')
                data = json.loads(response.data)

                schema = data['ebay_aspect_schema']
                brand_aspect = next((a for a in schema if a['name'] == 'Brand'), None)
                assert brand_aspect is not None
                assert brand_aspect.get('currentValue') == 'Sharpe', \
                    "Schema aspects should include currentValue from item_specifics"

                model_aspect = next((a for a in schema if a['name'] == 'Model'), None)
                assert model_aspect.get('currentValue') == '450'

                # Aspects not in item_specifics should have no currentValue
                power_aspect = next((a for a in schema if a['name'] == 'Power Source'), None)
                assert power_aspect.get('currentValue') is None
