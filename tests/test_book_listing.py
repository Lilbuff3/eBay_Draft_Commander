
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from backend.app.services.processor_service import ProcessorService
from backend.app.services.queue_manager import QueueJob


@pytest.fixture
def mock_deps():
    with patch('backend.app.services.processor_service.eBayService') as mock_ebay, \
         patch('backend.app.services.processor_service.AIAnalyzer') as mock_ai, \
         patch('backend.app.services.processor_service.PricingEngine') as mock_pricing, \
         patch('backend.app.services.processor_service.upload_folder') as mock_upload, \
         patch('backend.app.services.processor_service.get_template_manager') as mock_tmpl:

        # Setup basic successes for constructor
        mock_inventory = MagicMock()
        mock_inventory.create_inventory_item.return_value = ({}, 200)
        mock_inventory.create_offer.return_value = ({'offerId': 'OFFER_ABC'}, 200)
        mock_ebay.return_value.inventory_service = mock_inventory
        mock_ebay.return_value.publish_listing.return_value = ({'listingId': 'LIST_XYZ'}, 200)

        mock_pricing.return_value.get_price_with_comps.return_value = {"suggested_price": "25.00"}
        mock_upload.return_value = ["img.jpg"]
        mock_tmpl.return_value.render_description.return_value = "<html>Test</html>"

        yield {
            'ai': mock_ai.return_value,
            'ebay': mock_ebay.return_value,
            'pricing': mock_pricing.return_value,
            'inventory': mock_inventory,
        }


def _make_flask_app():
    """Return a minimal Flask app with required eBay config keys."""
    app = Flask(__name__)
    app.config['EBAY_MERCHANT_LOCATION'] = 'DEFAULT'
    app.config['EBAY_FULFILLMENT_POLICY'] = 'SHIP_TEST'
    app.config['EBAY_PAYMENT_POLICY'] = 'PAY_TEST'
    app.config['EBAY_RETURN_POLICY'] = 'RET_TEST'
    return app


# ---------------------------------------------------------------------------
# Test 1: book listing skips AI analysis
# ---------------------------------------------------------------------------

def test_book_listing_skips_ai_analysis(mock_deps, tmp_path):
    """
    When listing_type is 'book' and all data is pre-populated in job_metadata,
    ProcessorService should bypass the Gemini AI analysis step entirely.
    """
    # Arrange — dummy image so the 'no images' guard passes
    (tmp_path / "cover.jpg").touch()

    mock_deps['ebay'].create_listing_bundle.return_value = {
        'success': True,
        'listing_id': 'LIST_001',
        'offer_id': 'OFFER_001',
        'status': 'draft',
    }

    job = QueueJob(
        id="BOOK001",
        folder_path=str(tmp_path),
        folder_name=tmp_path.name,
        job_metadata={
            'listing_type': 'book',
            'isbn': '9780131103627',
            'item_specifics': {'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
            'source_data': {'title': 'The C Programming Language'},
        },
        user_title="The C Programming Language",
        user_price="25.00",
        user_condition="USED_GOOD",
        user_description="Classic programming book",
        item_specifics={'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
    )

    service = ProcessorService()
    app = _make_flask_app()
    with app.app_context():
        result = service.create_listing(job)

    # Assert AI was NOT called
    mock_deps['ai'].analyze_with_research.assert_not_called()

    # Assert listing succeeded
    assert result['success'] is True


# ---------------------------------------------------------------------------
# Test 2: book listing uses ISBN-aware pricing when no user_price is provided
# ---------------------------------------------------------------------------

def test_book_listing_uses_isbn_pricing(mock_deps, tmp_path):
    """
    When listing_type is 'book' and no user_price is supplied, the pricing
    engine should be called with isbn= so it can look up book-specific comps.
    """
    (tmp_path / "cover.jpg").touch()

    mock_deps['ebay'].create_listing_bundle.return_value = {
        'success': True,
        'listing_id': 'LIST_002',
        'offer_id': 'OFFER_002',
        'status': 'draft',
    }

    job = QueueJob(
        id="BOOK002",
        folder_path=str(tmp_path),
        folder_name=tmp_path.name,
        job_metadata={
            'listing_type': 'book',
            'isbn': '9780131103627',
            'item_specifics': {'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
            'source_data': {'title': 'The C Programming Language'},
        },
        user_title="The C Programming Language",
        user_price=None,  # No price override — must use pricing engine
        user_condition="USED_GOOD",
        user_description="Classic programming book",
        item_specifics={'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
    )

    service = ProcessorService()
    app = _make_flask_app()
    with app.app_context():
        service.create_listing(job)

    # Assert pricing engine was called at least once with isbn= in the kwargs.
    # The book fast path calls get_price_with_comps twice: first via
    # _determine_final_pricing (generic, no ISBN) and then again with the
    # ISBN for book-specific comp lookup.  We verify that at least one of
    # those calls carried isbn='9780131103627'.
    all_calls = mock_deps['pricing'].get_price_with_comps.call_args_list
    assert len(all_calls) >= 1, "Expected get_price_with_comps to be called at least once"
    isbn_calls = [c for c in all_calls if c.kwargs.get('isbn') == '9780131103627']
    assert len(isbn_calls) >= 1, (
        f"Expected at least one get_price_with_comps call with isbn='9780131103627'.\n"
        f"All calls: {all_calls}"
    )


# ---------------------------------------------------------------------------
# Test 3: book listing uses eBay Books category ID "267"
# ---------------------------------------------------------------------------

def test_book_listing_uses_book_category(mock_deps, tmp_path):
    """
    When listing_type is 'book', the offer payload passed to create_listing_bundle
    should use eBay's Books category ID of '267'.
    """
    (tmp_path / "cover.jpg").touch()

    mock_deps['ebay'].create_listing_bundle.return_value = {
        'success': True,
        'listing_id': 'LIST_003',
        'offer_id': 'OFFER_003',
        'status': 'draft',
    }

    job = QueueJob(
        id="BOOK003",
        folder_path=str(tmp_path),
        folder_name=tmp_path.name,
        job_metadata={
            'listing_type': 'book',
            'isbn': '9780131103627',
            'item_specifics': {'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
            'source_data': {'title': 'The C Programming Language'},
        },
        user_title="The C Programming Language",
        user_price="25.00",
        user_condition="USED_GOOD",
        user_description="Classic programming book",
        item_specifics={'Author': 'Kernighan', 'Publisher': 'Prentice Hall'},
    )

    service = ProcessorService()
    app = _make_flask_app()
    with app.app_context():
        service.create_listing(job)

    # Assert create_listing_bundle was called
    mock_deps['ebay'].create_listing_bundle.assert_called_once()
    bundle_call = mock_deps['ebay'].create_listing_bundle.call_args

    offer_data = bundle_call.kwargs.get('offer_data')
    assert offer_data is not None, "offer_data kwarg was not passed to create_listing_bundle"
    assert offer_data.get('categoryId') == "267", (
        f"Expected Books categoryId '267', got: {offer_data.get('categoryId')!r}"
    )
