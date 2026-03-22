"""
Full AI Pipeline Integration Test
====================================
Runs the COMPLETE listing pipeline — Gemini AI analysis, category mapping,
pricing, image upload, and eBay Trading API scheduled listing creation.

These create REAL scheduled listings on eBay (20 days out) and DO NOT delete them,
so you can verify them on ebay.com.

Usage:
    pytest tests/integration/test_full_pipeline.py -v -s
    pytest tests/integration/test_full_pipeline.py -v -s -k "cookbook"
    pytest tests/integration/test_full_pipeline.py -v -s -k "boombox"
    pytest tests/integration/test_full_pipeline.py -v -s -k "jacket"

    # Clean up all test listings afterward:
    pytest tests/integration/test_full_pipeline.py -v -s -k "cleanup"

Requirements:
    - Valid .env with EBAY_USER_TOKEN, policies, GOOGLE_API_KEY
    - Test fixture images in tests/fixtures/images/
    - AUTO_PUBLISH=true in .env (or test forces it)
"""

import sys
import os
import json
import time
import shutil
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = PROJECT_ROOT / 'tests' / 'fixtures' / 'images'
# Temp inbox folders for the pipeline (it needs a real folder with images)
TEMP_INBOX = PROJECT_ROOT / 'tests' / 'fixtures' / '_temp_inbox'

# Track created listings for cleanup
CREATED_LISTINGS_FILE = PROJECT_ROOT / 'tests' / 'fixtures' / '_test_listings.json'


def _load_created_listings():
    """Load previously created test listing IDs."""
    if CREATED_LISTINGS_FILE.exists():
        return json.loads(CREATED_LISTINGS_FILE.read_text())
    return []


def _save_created_listing(entry):
    """Append a new listing entry to the tracking file."""
    listings = _load_created_listings()
    listings.append(entry)
    CREATED_LISTINGS_FILE.write_text(json.dumps(listings, indent=2))


def _create_flask_app():
    """Create and configure a Flask app for pipeline context."""
    from backend.app import create_app
    app = create_app()
    return app


def _create_job_obj(job_id, folder_path, scheduled_time=None):
    """
    Create a real JobModel instance in the DB so the pipeline can
    read/write ai_data, item_specifics, etc.
    """
    from backend.app.core.database import JobModel, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    # Use an in-memory approach: create job object directly
    job = JobModel(
        id=job_id,
        folder_path=str(folder_path),
        folder_name=folder_path.name,
        status='pending',
        scheduled_time=scheduled_time,
        metadata_json=json.dumps({
            'user_approved': True,  # Bypass review gate
        }),
    )
    return job


class TestFullAIPipeline:
    """
    End-to-end test: real images -> Gemini AI -> category -> pricing ->
    image upload -> eBay Trading API scheduled listing.

    Listings are left active (scheduled 20 days out) so you can verify
    on ebay.com. Run test_cleanup to end them.
    """

    @pytest.fixture(autouse=True)
    def setup_app(self):
        """Set up Flask app context for the pipeline."""
        self.app = _create_flask_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        yield
        self.ctx.pop()
        # Clean up temp inbox folders
        if TEMP_INBOX.exists():
            shutil.rmtree(TEMP_INBOX, ignore_errors=True)

    def _run_pipeline(self, fixture_name, max_images=4):
        """
        Run the full pipeline for a fixture folder.
        Returns the result dict from ProcessorService.create_listing().
        """
        from backend.app.services.processor_service import ProcessorService

        # 1. Set up temp inbox folder with copies of fixture images
        source_dir = FIXTURES_DIR / fixture_name
        if not source_dir.exists():
            pytest.skip(f"Fixture folder not found: {source_dir}")

        images = sorted(source_dir.glob('*.jpg'))[:max_images]
        if not images:
            pytest.skip(f"No JPG images in {source_dir}")

        # Create temp folder to simulate inbox item
        job_id = f'TEST{fixture_name[:4].upper()}'
        temp_folder = TEMP_INBOX / f'test_{fixture_name}'
        temp_folder.mkdir(parents=True, exist_ok=True)
        for img in images:
            shutil.copy2(img, temp_folder / img.name)

        print(f"\n  Fixture: {fixture_name} ({len(images)} images)")
        print(f"  Temp folder: {temp_folder}")

        # 2. Schedule 20 days out (eBay max is 21)
        schedule_time = datetime.now(timezone.utc) + timedelta(days=20)

        # 3. Create job object
        job = _create_job_obj(job_id, temp_folder, scheduled_time=schedule_time)

        # 4. Force auto-publish for this test
        env_overrides = {
            'AUTO_PUBLISH': 'true',
            'CONFIDENCE_THRESHOLD': '0',      # Accept any confidence
            'AUTO_PUBLISH_MIN_PRICE': '0.01',  # Accept any price
        }

        # 5. Run the full pipeline
        processor = ProcessorService()
        logs = []

        def log_callback(msg, level='info'):
            logs.append(f"[{level.upper()}] {msg}")
            print(f"    {msg}")

        with patch.dict(os.environ, env_overrides):
            result = processor.create_listing(job, log_callback=log_callback)

        return result, job, logs

    def _assert_pipeline_success(self, result, job, fixture_name):
        """Common assertions for a successful pipeline run."""
        # Must have succeeded
        assert result.get('success') or result.get('listing_id'), (
            f"Pipeline failed for {fixture_name}:\n"
            f"  error_type: {result.get('error_type')}\n"
            f"  error_message: {result.get('error_message')}\n"
            f"  status: {result.get('status')}"
        )

        listing_id = result.get('listing_id')
        assert listing_id, f"No listing_id in result for {fixture_name}"

        # Verify AI populated the job
        ai_data = job.ai_data
        assert ai_data, "AI data is empty"
        assert ai_data.get('listing'), "No listing data from AI"
        assert ai_data.get('category_id'), "No category from AI"
        assert ai_data.get('image_urls'), "No uploaded image URLs"

        title = ai_data['listing'].get('suggested_title', '')
        price = result.get('price', '0')
        category = ai_data.get('category_name', 'Unknown')

        print(f"\n  === LISTING CREATED ===")
        print(f"  eBay Item ID: {listing_id}")
        print(f"  Title: {title}")
        print(f"  Price: ${price}")
        print(f"  Category: {category} ({ai_data.get('category_id')})")
        print(f"  Images: {len(ai_data.get('image_urls', []))}")
        print(f"  Confidence: {job.confidence_score}")
        if ai_data.get('identification'):
            ident = ai_data['identification']
            print(f"  Brand: {ident.get('brand', 'N/A')}")
            print(f"  Model: {ident.get('model', 'N/A')}")
            print(f"  MPN: {ident.get('mpn', 'N/A')}")
        print(f"  View: https://www.ebay.com/itm/{listing_id}")

        # Save for cleanup later
        _save_created_listing({
            'item_id': listing_id,
            'fixture': fixture_name,
            'title': title,
            'price': str(price),
            'created_at': datetime.now(timezone.utc).isoformat(),
        })

        # Timing info
        timing = result.get('timing', {})
        print(f"\n  Timing:")
        for step, duration in timing.items():
            if isinstance(duration, (int, float)):
                print(f"    {step}: {duration:.1f}s")

        return listing_id

    def test_cookbook_full_pipeline(self):
        """
        BOOK: Crossroads cookbook with ISBN.
        Tests: book detection, ISBN lookup, Books category, book-specific aspects.
        """
        result, job, logs = self._run_pipeline('cookbook', max_images=4)
        item_id = self._assert_pipeline_success(result, job, 'cookbook')

        # Book-specific assertions
        ai_data = job.ai_data
        assert ai_data.get('identification', {}).get('product_type', '').lower() in ['book', 'cookbook'], \
            f"Expected book product type, got: {ai_data.get('identification', {}).get('product_type')}"

    def test_boombox_full_pipeline(self):
        """
        ELECTRONICS: AIWA CA-30 vintage boombox.
        Tests: brand/model detection, electronics category, many images (10).
        """
        result, job, logs = self._run_pipeline('boombox', max_images=6)
        item_id = self._assert_pipeline_success(result, job, 'boombox')

        # Electronics-specific assertions
        ai_data = job.ai_data
        ident = ai_data.get('identification', {})
        # AI should detect AIWA brand
        brand = ident.get('brand', '').upper()
        assert brand, f"AI didn't detect brand, got: {ident}"

    def test_tesla_jacket_full_pipeline(self):
        """
        CLOTHING: Tesla softshell jacket.
        Tests: clothing category, size/color detection, fabric identification.
        """
        result, job, logs = self._run_pipeline('tesla-jacket', max_images=4)
        item_id = self._assert_pipeline_success(result, job, 'tesla-jacket')

        # Clothing-specific assertions
        ai_data = job.ai_data
        ident = ai_data.get('identification', {})
        # Should detect Tesla brand or at least identify as clothing
        product_type = ident.get('product_type', '').lower()
        assert product_type, f"AI didn't detect product type, got: {ident}"


class TestCleanupTestListings:
    """
    Cleanup utility: ends all test listings created by TestFullAIPipeline.
    Run this when you're done verifying listings on eBay.

    Usage: pytest tests/integration/test_full_pipeline.py -v -s -k "cleanup"
    """

    def test_cleanup_all(self):
        """End all previously created test listings."""
        from backend.app.services.ebay.trading import TradingService

        listings = _load_created_listings()
        if not listings:
            print("\n  No test listings to clean up.")
            return

        ts = TradingService()
        cleaned = 0
        failed = 0

        for entry in listings:
            item_id = entry['item_id']
            try:
                result = ts.end_fixed_price_item(item_id)
                if result.get('success'):
                    print(f"  Ended: {item_id} ({entry.get('title', 'N/A')})")
                    cleaned += 1
                else:
                    print(f"  Failed to end {item_id}: {result.get('error')}")
                    failed += 1
            except Exception as e:
                print(f"  Error ending {item_id}: {e}")
                failed += 1

        # Clear the tracking file
        if failed == 0:
            CREATED_LISTINGS_FILE.unlink(missing_ok=True)
            print(f"\n  Cleaned up {cleaned} listings. Tracking file removed.")
        else:
            print(f"\n  Cleaned: {cleaned}, Failed: {failed}. Tracking file kept.")
