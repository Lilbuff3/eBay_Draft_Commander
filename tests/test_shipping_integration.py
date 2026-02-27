import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from backend.app.services.processor_service import ProcessorService
from backend.app.services.queue_job import QueueJob

def test_full_shipping_flow():
    print("=== Testing Full Shipping Cost Flow ===")
    
    # 1. Setup mocks to avoid real AI/API calls
    processor = ProcessorService()
    
    # Mock AI Agent analysis result
    mock_analysis = {
        'success': True,
        'title': 'Test Board Game (Heavy)',
        'raw_description': 'A heavy board game',
        'ai_suggested_price': 50.00,
        'item_specifics': {},
        'shipping_cost': 15.00,  # AI detected a heavy item
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
    processor.ai_agent.analyze_item = MagicMock(return_value=mock_analysis)
    
    # Mock Pricing Engine to see what it suggested
    # The PricingEngine.get_price_with_comps method should receive shipping_cost=15.00
    mock_pricing_result = {
        'suggested_price': 65.00, # 50 + 15
        'source': 'test',
        'reasoning': 'Mocked reasoning',
        'timing': 0.1
    }
    processor.ai_agent.pricing_engine.get_price_with_comps = MagicMock(return_value=mock_pricing_result)
    
    # Mock other dependencies
    processor.category_mapper.get_category = MagicMock(return_value={'id': '123', 'name': 'Games'})
    processor.image_processor.upload_images = MagicMock(return_value={'urls': [], 'timing': 0.1})
    processor._render_listing_template = MagicMock(return_value={'html': '', 'timing': 0.1})
    processor._create_trading_api_listing = MagicMock(return_value={'success': True, 'listing_id': 'LIST123', 'status': 'Created', 'timing': 0.1})
    
    # 2. Create a mock job
    job = MagicMock()
    job.id = "JOB1"
    job.folder_path = "tests/mock_folder"
    job.user_price = None
    job.user_condition = None
    job.job_metadata = {}
    job.ai_data = {}
    
    # Create the folder if it doesn't exist for Path(job.folder_path).exists()
    Path("tests/mock_folder").mkdir(exist_ok=True)
    # Add a dummy image
    (Path("tests/mock_folder") / "test_image.jpg").touch()
    
    print("Running processor.create_listing...")
    result = processor.create_listing(job)
    
    # 3. Verify
    print("\nVerification:")
    # Check if pricing engine was called with the correct shipping cost
    args, kwargs = processor.ai_agent.pricing_engine.get_price_with_comps.call_args
    called_shipping_cost = kwargs.get('shipping_cost')
    
    if called_shipping_cost == 15.00:
        print(f"✅ PricingEngine called with dynamic shipping_cost: ${called_shipping_cost:.2f}")
    else:
        print(f"❌ PricingEngine called with INCORRECT shipping_cost: {called_shipping_cost}")

    if float(result.get('price')) == 65.00:
        print(f"✅ Final price includes shipping buffer: ${result.get('price')}")
    else:
        print(f"❌ Final price does NOT match expected: {result.get('price')}")
    
    # 4. Test Fallback (AI returns no shipping data)
    print("\n--- Testing Fallback Flow ---")
    mock_analysis_no_shipping = mock_analysis.copy()
    mock_analysis_no_shipping['shipping_cost'] = processor.ai_agent._default_shipping_cost # Fallback logic already handled in Agent
    processor.ai_agent.analyze_item = MagicMock(return_value=mock_analysis_no_shipping)
    
    mock_pricing_result_fallback = {
        'suggested_price': 56.50, # 50 + 6.50 (default)
        'source': 'test-fallback'
    }
    processor.ai_agent.pricing_engine.get_price_with_comps = MagicMock(return_value=mock_pricing_result_fallback)
    
    result_fallback = processor.create_listing(job)
    args_fb, kwargs_fb = processor.ai_agent.pricing_engine.get_price_with_comps.call_args
    called_fb_shipping = kwargs_fb.get('shipping_cost')
    
    if called_fb_shipping == processor.ai_agent._default_shipping_cost:
        print(f"✅ Fallback to default shipping: ${called_fb_shipping:.2f}")
    else:
        print(f"❌ INCORRECT fallback shipping: {called_fb_shipping}")
        
    # Cleanup
    (Path("tests/mock_folder") / "test_image.jpg").unlink()
    Path("tests/mock_folder").rmdir()
    
    return called_shipping_cost == 15.00 and float(result.get('price')) == 65.00 and called_fb_shipping == processor.ai_agent._default_shipping_cost

if __name__ == "__main__":
    if test_full_shipping_flow():
        print("\nIntegration Test PASSED")
        sys.exit(0)
    else:
        print("\nIntegration Test FAILED")
        sys.exit(1)
