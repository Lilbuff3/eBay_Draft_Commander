
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[0]))

from backend.app.services.listing_ai_agent import ListingAIAgent
from backend.app.services.processor_service import ProcessorService

def test_category_selection_logic():
    print("\n--- Testing Phase 2 Category Selection Logic ---\n")
    
    # Mock dependencies
    mock_job = MagicMock()
    mock_job.user_title = None
    mock_job.folder_path = "C:/fake/path/Laser Printer Drum"
    mock_job.ai_data = {}
    mock_job.confidence_score = 0.9
    mock_job.user_condition = "NEW"
    mock_job.scheduled_time = None
    
    # 1. Test Ambiguous Item: Laser Printer Drum
    with patch('backend.app.services.ebay.taxonomy.get_category_suggestions') as mock_sug:
        mock_sug.return_value = [
            {'category_id': '51288', 'full_path': 'Computers > Printers > Parts > Laser Drums'},
            {'category_id': '38092', 'full_path': 'Musical Instruments > Percussion > Drums'}
        ]
        
        agent = ListingAIAgent()
        # Mocking the actual AI analysis to simulate Gemini's choice
        with patch.object(agent.ai_analyzer, 'analyze_with_research') as mock_analyze:
            mock_analyze.return_value = {
                'identification': {
                    'brand': 'HP',
                    'model': 'CB384A',
                    'category_id': '51288'
                },
                'listing': {
                    'suggested_title': 'HP CB384A Laser Printer Drum',
                    'suggested_price': 89.99,
                    'confidence_score': 0.95
                },
                'item_specifics': {'Brand': 'HP', 'Type': 'Drum'}
            }
            
            # Analyze
            result = agent.analyze_item(mock_job, ['img1.jpg'], "NEW")
            
            print(f"Test case 1 (Printer Drum):")
            print(f"  Expected Category ID: 51288")
            print(f"  AI Selected ID: {result.get('category_id')}")
            assert result.get('category_id') == '51288'
            print("  [PASS]")

    # 2. Test Ambiguous Item: Snare Drum
    with patch('backend.app.services.ebay.taxonomy.get_category_suggestions') as mock_sug:
        mock_sug.return_value = [
            {'category_id': '51288', 'full_path': 'Computers > Printers > Parts > Laser Drums'},
            {'category_id': '38092', 'full_path': 'Musical Instruments > Percussion > Drums'}
        ]
        
        agent = ListingAIAgent()
        with patch.object(agent.ai_analyzer, 'analyze_with_research') as mock_analyze:
            mock_analyze.return_value = {
                'identification': {
                    'brand': 'Ludwig',
                    'model': 'Supraphonic',
                    'category_id': '38092'
                },
                'listing': {
                    'suggested_title': 'Ludwig Supraphonic Snare Drum',
                    'suggested_price': 450.00,
                    'confidence_score': 0.98
                },
                'item_specifics': {'Brand': 'Ludwig', 'Type': 'Snare Drum'}
            }
            
            # Analyze
            result = agent.analyze_item(mock_job, ['img1.jpg'], "NEW")
            
            print(f"\nTest case 2 (Musical Drum):")
            print(f"  Expected Category ID: 38092")
            print(f"  AI Selected ID: {result.get('category_id')}")
            assert result.get('category_id') == '38092'
            print("  [PASS]")

    # 3. Test IRRELEVANT suggestions -> NULL category
    with patch('backend.app.services.ebay.taxonomy.get_category_suggestions') as mock_sug:
        mock_sug.return_value = [
            {'category_id': '1', 'full_path': 'Clothing > Shoes'},
            {'category_id': '2', 'full_path': 'Home > Garden'}
        ]
        
        agent = ListingAIAgent()
        with patch.object(agent.ai_analyzer, 'analyze_with_research') as mock_analyze:
            mock_analyze.return_value = {
                'identification': {
                    'brand': 'N/A',
                    'model': 'Mysterious Object',
                    'category_id': None # LLM returns null because suggestions suck
                },
                'listing': {
                    'suggested_title': 'Ancient Alien Artifact',
                    'suggested_price': 1000000.00,
                    'confidence_score': 0.5
                },
                'item_specifics': {}
            }
            
            result = agent.analyze_item(mock_job, ['img1.jpg'], "USED")
            
            print(f"\nTest case 3 (Irrelevant Suggestions):")
            print(f"  Expected Category ID: None")
            print(f"  AI Selected ID: {result.get('category_id')}")
            assert result.get('category_id') is None
            print("  [PASS]")

    # 4. Test Processor Service PENDING_REVIEW logic
    processor = ProcessorService()
    # Mocking all internal calls of create_listing to isolate the review logic
    with patch.object(processor.ai_agent, 'analyze_item') as mock_ai:
        mock_ai.return_value = {
            'success': True,
            'title': 'Test Item',
            'raw_description': 'Test Desc',
            'item_specifics': {},
            'ai_suggested_price': 10.00,
            'confidence_score': 0.99, # High confidence
            'category_id': None # BUT missing category
        }
        with patch.object(processor.ai_agent, 'get_final_pricing') as mock_price:
            mock_price.return_value = {"price": "10.00", "timing": 0}
            with patch.object(processor.image_processor, 'upload_images') as mock_upload:
                mock_upload.return_value = {"urls": [], "timing": 0}
                
                job_obj = MagicMock()
                job_obj.folder_path = "C:/tmp"
                # Step A: Get a preliminary title or use folder name for suggestions
                temp_title = job_obj.user_title or "Fake Folder Name"
                job_obj.user_condition = "NEW"
                job_obj.job_metadata = {}
                
                # Mock Path.exists
                with patch('pathlib.Path.exists') as mock_exists:
                    mock_exists.return_value = True
                    # Mock finding images
                    with patch('pathlib.Path.iterdir') as mock_iter:
                        mock_file = MagicMock()
                        mock_file.suffix = '.jpg'
                        mock_iter.return_value = [mock_file]
                        
                        res = processor.create_listing(job_obj)
                        
                        print(f"\nTest case 4 (Processor Service Gateway):")
                        print(f"  High confidence (0.99) BUT missing category.")
                        print(f"  Expected Status: pending_review")
                        print(f"  Actual Status: {res.get('status')}")
                        assert res.get('status') == 'pending_review'
                        print("  [PASS]")

if __name__ == "__main__":
    try:
        test_category_selection_logic()
        print("\nALL TESTS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR DURING TESTING: {e}")
        sys.exit(1)
