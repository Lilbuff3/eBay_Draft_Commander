import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
# File is at root/tests/unit/test_...py, so parents[2] is root
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.processor_service import ProcessorService


class TestShippingIntegration:
    """Integration tests for the full shipping cost flow through the processing pipeline."""

    def setup_method(self):
        self.processor = ProcessorService()
        # Create mock folder for test
        self.mock_folder = Path("tests/mock_folder")
        self.mock_folder.mkdir(parents=True, exist_ok=True)
        (self.mock_folder / "test_image.jpg").touch()

    def teardown_method(self):
        # Cleanup
        mock_image = self.mock_folder / "test_image.jpg"
        if mock_image.exists():
            mock_image.unlink()
        if self.mock_folder.exists():
            self.mock_folder.rmdir()

    def _setup_mocks(self, mock_analysis, mock_pricing_result):
        """Set up common mocks to avoid real AI/API calls."""
        self.processor.ai_agent.analyze_item = MagicMock(return_value=mock_analysis)
        self.processor.ai_agent.pricing_engine.get_price_with_comps = MagicMock(return_value=mock_pricing_result)
        self.processor.category_mapper.get_category = MagicMock(return_value={'id': '123', 'name': 'Games'})
        self.processor.image_processor.upload_images = MagicMock(return_value={'urls': [], 'timing': 0.1})
        self.processor._render_listing_template = MagicMock(return_value={'html': '', 'timing': 0.1})
        self.processor._create_trading_api_listing = MagicMock(return_value={'success': True, 'listing_id': 'LIST123', 'status': 'Created', 'timing': 0.1})

    def _create_mock_job(self, ai_data=None):
        """Create a mock job object."""
        job = MagicMock()
        job.id = "JOB1"
        job.folder_path = str(self.mock_folder)
        job.user_price = None
        job.user_condition = 'USED_GOOD'
        job.job_metadata = {}
        job.ai_data = ai_data if ai_data is not None else {}
        return job

    def test_heavy_item_shipping_cost_passed_to_pricing(self):
        """Verify that AI-detected shipping cost is passed to the pricing engine."""
        mock_analysis = {
            'success': True,
            'title': 'Test Board Game (Heavy)',
            'raw_description': 'A heavy board game',
            'ai_suggested_price': 50.00,
            'item_specifics': {},
            'shipping_cost': 15.00,
            'ai_data': {
                'identification': {
                    'package_size': 'heavy',
                    'estimated_weight_lbs': 12.0
                },
                'listing': {
                    'suggested_title': 'Test Board Game (Heavy)',
                    'suggested_price': 50.00
                }
            }
        }
        mock_pricing_result = {
            'suggested_price': 65.00,
            'source': 'test',
            'reasoning': 'Mocked reasoning',
            'timing': 0.1
        }

        self._setup_mocks(mock_analysis, mock_pricing_result)
        # Pre-populate ai_data with identification so shipping recalculation
        # after category detection can read package_size/weight
        job = self._create_mock_job(ai_data={
            'identification': {
                'package_size': 'heavy',
                'estimated_weight_lbs': 12.0
            }
        })
        result = self.processor.create_listing(job)

        _, kwargs = self.processor.ai_agent.pricing_engine.get_price_with_comps.call_args
        assert kwargs.get('shipping_cost') == 15.00
        assert float(result.get('price')) == 65.00

    def test_fallback_shipping_cost(self):
        """Verify fallback to default shipping cost when AI provides no shipping data."""
        default_shipping = self.processor.ai_agent._default_shipping_cost

        mock_analysis = {
            'success': True,
            'title': 'Test Item (Default Shipping)',
            'raw_description': 'An item with default shipping',
            'ai_suggested_price': 50.00,
            'item_specifics': {},
            'shipping_cost': default_shipping,
            'ai_data': {
                'identification': {
                    'package_size': 'medium',
                    'estimated_weight_lbs': 1.5
                },
                'listing': {
                    'suggested_title': 'Test Item (Default Shipping)',
                    'suggested_price': 50.00
                }
            }
        }
        mock_pricing_result = {
            'suggested_price': 56.50,
            'source': 'test-fallback'
        }

        self._setup_mocks(mock_analysis, mock_pricing_result)
        job = self._create_mock_job()
        self.processor.create_listing(job)

        _, kwargs = self.processor.ai_agent.pricing_engine.get_price_with_comps.call_args
        assert kwargs.get('shipping_cost') == default_shipping
