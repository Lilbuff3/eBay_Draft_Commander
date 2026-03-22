"""
Live Pipeline Integration Test
================================
Creates REAL eBay listings using test fixture images, verifies success,
then immediately ends the listings to clean up.

Usage:
    pytest tests/integration/test_live_pipeline.py -v
    pytest tests/integration/test_live_pipeline.py -v -k "cookbook"
    pytest tests/integration/test_live_pipeline.py -v -k "boombox"

Requirements:
    - Valid .env with EBAY_USER_TOKEN, policies, GOOGLE_API_KEY
    - Test fixture images in tests/fixtures/images/
"""

import sys
import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.ebay.trading import TradingService
from backend.app.services.ebay.media import upload_image_to_eps
from backend.app.services.ebay.policies import load_env

FIXTURES_DIR = PROJECT_ROOT / 'tests' / 'fixtures' / 'images'


def _get_policies():
    """Load eBay business policies from .env"""
    creds = load_env()
    policies = {
        'payment_policy_id': creds.get('EBAY_PAYMENT_POLICY'),
        'return_policy_id': creds.get('EBAY_RETURN_POLICY'),
        'fulfillment_policy_id': creds.get('EBAY_FULFILLMENT_POLICY'),
    }
    missing = [k for k, v in policies.items() if not v]
    if missing:
        pytest.skip(f"Missing policies in .env: {missing}")
    return policies


def _upload_fixture_images(folder_name, max_images=2):
    """Upload fixture images to eBay EPS, return list of URLs."""
    folder = FIXTURES_DIR / folder_name
    if not folder.exists():
        pytest.skip(f"Fixture folder not found: {folder}")

    images = sorted(folder.glob('*.jpg'))[:max_images]
    if not images:
        pytest.skip(f"No JPG images in {folder}")

    urls = []
    for img_path in images:
        url = upload_image_to_eps(str(img_path))
        assert url is not None, f"Failed to upload {img_path.name}"
        urls.append(url)

    return urls


# -- Test item profiles (pre-baked metadata, no AI needed) --

TEST_ITEMS = {
    'cookbook': {
        'folder': 'cookbook',
        'title': 'Crossroads Cookbook by Tal Ronnen Hardcover',
        'description': '<p>Crossroads cookbook. Good condition.</p>',
        'category_id': '261186',  # Cookbooks
        'condition_id': '4000',   # Very Good
        'price': '9.99',
        'item_specifics': {
            'Brand': 'Unbranded',
            'Book Title': 'Crossroads',
            'Author': 'Tal Ronnen',
            'Language': 'English',
            'Topic': 'Cooking',
        },
    },
    'boombox': {
        'folder': 'boombox',
        'title': 'AIWA CA-30 Carry Component System Boombox Stereo',
        'description': '<p>AIWA CA-30 vintage boombox stereo system.</p>',
        'category_id': '175721',  # Portable Audio - Boomboxes
        'condition_id': '3000',   # Used
        'price': '14.99',
        'item_specifics': {
            'Brand': 'AIWA',
            'Type': 'Boombox',
            'MPN': 'CA-30',
            'Connectivity': 'Wired',
        },
    },
    'tesla-jacket': {
        'folder': 'tesla-jacket',
        'title': 'Tesla Athletic Shorts Black Zippered Pocket Mens Large',
        'description': '<p>Tesla brand athletic shorts in black with zippered pocket.</p>',
        'category_id': '260957',  # Activewear > Men's Clothing > Activewear Shorts
        'condition_id': '3000',   # Used
        'price': '9.99',
        'item_specifics': {
            'Brand': 'Tesla',
            'Color': 'Black',
            'Type': 'Shorts',
            'Size': 'L',
            'Size Type': 'Regular',
            'Department': 'Men',
            'Style': 'Athletic',
            'Material': 'Polyester',
            'Inseam': '7 in',
            'Features': 'Pockets',
        },
    },
}


class TestLivePipeline:
    """
    End-to-end test: upload images -> create listing -> verify -> end listing.

    Each test creates a REAL eBay listing scheduled 30 days out,
    asserts it was created successfully, then immediately ends it.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.trading = TradingService()
        self.policies = _get_policies()
        self.created_items = []  # Track for cleanup
        yield
        # Cleanup: end any listings that weren't cleaned up in the test
        for item_id in self.created_items:
            try:
                self.trading.end_fixed_price_item(item_id)
            except Exception:
                pass

    def _create_and_verify(self, profile_name, max_images=2):
        """
        Core test flow for any item profile.
        Returns the item_id for additional assertions if needed.
        """
        profile = TEST_ITEMS[profile_name]

        # Step 1: Upload images
        image_urls = _upload_fixture_images(profile['folder'], max_images=max_images)
        assert len(image_urls) >= 1, "At least one image must upload"

        # Step 2: Build item data
        sku = f'DC-TEST-{profile_name[:8].upper()}'
        # eBay max schedule is 21 days; use 3 weeks minus a buffer
        schedule_time = (
            datetime.now(timezone.utc) + timedelta(days=20)
        ).strftime('%Y-%m-%dT%H:%M:%S.000Z')

        item_data = {
            'title': profile['title'],
            'description': profile['description'],
            'category_id': profile['category_id'],
            'condition_id': profile['condition_id'],
            'price': profile['price'],
            'sku': sku,
            'image_urls': image_urls,
            'item_specifics': profile['item_specifics'],
            **self.policies,
        }

        # Step 3: Create listing (scheduled 30 days out)
        result = self.trading.add_fixed_price_item(item_data, schedule_time=schedule_time)

        assert result['success'] is True, f"AddFixedPriceItem failed: {result.get('error')}"
        assert result.get('item_id'), "No item_id returned"
        assert result.get('status') == 'Scheduled', f"Expected Scheduled, got {result.get('status')}"

        item_id = result['item_id']
        self.created_items.append(item_id)
        print(f"\n  Created listing {item_id} (SKU: {sku}, scheduled +30d)")

        # Step 4: End the listing immediately
        end_result = self.trading.end_fixed_price_item(item_id)
        assert end_result['success'] is True, f"EndFixedPriceItem failed: {end_result.get('error')}"
        self.created_items.remove(item_id)  # Cleaned up successfully
        print(f"  Ended listing {item_id} successfully")

        return item_id

    def test_cookbook(self):
        """Books category - cookbook with 2 images"""
        self._create_and_verify('cookbook', max_images=2)

    def test_boombox(self):
        """Electronics/Audio category - boombox with 3 images"""
        self._create_and_verify('boombox', max_images=3)

    def test_tesla_shorts(self):
        """Clothing category - athletic shorts with 2 images"""
        self._create_and_verify('tesla-jacket', max_images=2)


class TestGetSellerList:
    """Verify GetSellerList correctly parses titles, prices, and images."""

    def test_listings_have_real_data(self):
        """All listings should have real titles (not 'Legacy Item'), prices > 0, and images."""
        ts = TradingService()
        result, status = ts.get_active_listings_light()

        assert status == 200, f"GetSellerList failed: {result}"
        assert result['total'] > 0, "No listings found"

        legacy_count = 0
        zero_price_count = 0
        no_image_count = 0

        for item in result['listings']:
            if item['title'].startswith('Legacy Item'):
                legacy_count += 1
            if item['price'] == 0.0:
                zero_price_count += 1
            if item['imageUrl'] is None:
                no_image_count += 1

        total = result['total']
        print(f"\n  Total listings: {total}")
        print(f"  Legacy titles: {legacy_count}/{total}")
        print(f"  Zero prices: {zero_price_count}/{total}")
        print(f"  Missing images: {no_image_count}/{total}")

        # Allow a small tolerance for genuinely untitled/free items
        assert legacy_count < total * 0.05, f"{legacy_count}/{total} listings have fallback titles"
        assert zero_price_count < total * 0.05, f"{zero_price_count}/{total} listings have $0.00 price"
        assert no_image_count < total * 0.10, f"{no_image_count}/{total} listings have no image"
