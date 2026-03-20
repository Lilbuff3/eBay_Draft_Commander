# Migration API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend endpoints for `/api/migration/check` and `/api/migration/execute` so the existing `MigrationModal` frontend can scan eBay for legacy listings and import them into the Inventory API.

**Architecture:** New `migration_api.py` blueprint module in `backend/app/blueprints/api/`. Uses existing `TradingService.get_active_listings_light()` to fetch all active eBay listings, cross-references against local `jobs` table `listing_id` column to determine which are already tracked. Execute endpoint uses `InventoryService.create_inventory_item()` + `create_offer()` to import selected listings.

**Tech Stack:** Flask, SQLAlchemy, existing eBay Trading/Inventory service classes

---

### Task 1: Create migration_api.py with /api/migration/check endpoint

**Files:**
- Create: `backend/app/blueprints/api/migration_api.py`
- Modify: `backend/app/blueprints/api/__init__.py`
- Test: `tests/unit/test_migration_api.py`

**Step 1: Write the failing test**

Create `tests/unit/test_migration_api.py`:

```python
"""Tests for migration API endpoints"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    """Create test Flask app"""
    from backend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestMigrationCheck:
    """Tests for GET /api/migration/check"""

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_returns_items_with_inventory_flag(self, MockTrading, client, app):
        """Items already in local DB should have inInventory=True"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '111', 'title': 'Item A', 'price': 19.99, 'sku': 'DC-AAA', 'imageUrl': None},
                {'listingId': '222', 'title': 'Item B', 'price': 29.99, 'sku': None, 'imageUrl': None},
            ],
            'total': 2,
            'source': 'test'
        }, 200)

        # Seed a job with listing_id '111' so it counts as "in inventory"
        with app.app_context():
            from backend.app.core.database import db, JobModel
            db.create_all()
            job = JobModel(id='test0001', folder_path='/tmp/test', status='completed', listing_id='111')
            db.session.add(job)
            db.session.commit()

        resp = client.get('/api/migration/check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'items' in data
        assert len(data['items']) == 2

        item_a = next(i for i in data['items'] if i['listingId'] == '111')
        item_b = next(i for i in data['items'] if i['listingId'] == '222')
        assert item_a['inInventory'] is True
        assert item_b['inInventory'] is False

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_handles_trading_api_error(self, MockTrading, client):
        """Should return error JSON when Trading API fails"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({'error': 'No token'}, 500)

        resp = client.get('/api/migration/check')
        assert resp.status_code == 502
        data = resp.get_json()
        assert 'error' in data

    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_check_handles_no_listings(self, MockTrading, client):
        """Should return empty items list when no eBay listings exist"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({'error': 'No items found via Trading API'}, 404)

        resp = client.get('/api/migration/check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['items'] == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_migration_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.blueprints.api.migration_api'`

**Step 3: Write the migration_api.py implementation**

Create `backend/app/blueprints/api/migration_api.py`:

```python
from flask import Blueprint, jsonify, request
from backend.app.services.ebay.trading import TradingService
from backend.app.services.ebay.inventory import InventoryService
from backend.app.services.ebay.policies import load_env
from backend.app.core.database import db, JobModel
from backend.app.core.logger import get_logger
from .helpers import error_response

migration_bp = Blueprint('migration', __name__)
logger = get_logger('api.migration')


@migration_bp.route('/migration/check')
def check_legacy_listings():
    """
    Scan eBay account for active listings and flag which ones
    are already tracked in the local jobs database.

    Returns: { items: [{ listingId, title, price, sku, imageUrl, inInventory }] }
    """
    try:
        trading = TradingService()
        result, status = trading.get_active_listings_light()

        if status == 404:
            # No listings found — not an error, just empty
            return jsonify({'items': [], 'total': 0}), 200

        if status != 200:
            return error_response(
                result.get('error', 'Failed to fetch eBay listings'),
                502
            )

        listings = result.get('listings', [])

        # Get all listing_ids already tracked locally
        tracked_ids = set()
        try:
            rows = db.session.query(JobModel.listing_id).filter(
                JobModel.listing_id.isnot(None),
                JobModel.listing_id != ''
            ).all()
            tracked_ids = {r[0] for r in rows}
        except Exception as e:
            logger.warning(f"Could not query local jobs: {e}")

        # Build response matching frontend LegacyItem interface
        items = []
        for listing in listings:
            listing_id = listing.get('listingId', '')
            items.append({
                'listingId': listing_id,
                'title': listing.get('title', 'Untitled'),
                'price': listing.get('price', 0.0),
                'sku': listing.get('sku') or None,
                'imageUrl': listing.get('imageUrl') or None,
                'inInventory': listing_id in tracked_ids,
            })

        return jsonify({'items': items, 'total': len(items)}), 200

    except Exception as e:
        logger.exception("Migration check failed")
        return error_response(str(e))
```

**Step 4: Register the blueprint**

In `backend/app/blueprints/api/__init__.py`, add:

```python
from .migration_api import migration_bp
```

And register it:

```python
api_bp.register_blueprint(migration_bp, url_prefix='')
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_migration_api.py -v`
Expected: 3 tests PASS

**Step 6: Commit**

```bash
git add backend/app/blueprints/api/migration_api.py backend/app/blueprints/api/__init__.py tests/unit/test_migration_api.py
git commit -m "feat: add /api/migration/check endpoint for legacy listing scan"
```

---

### Task 2: Add /api/migration/execute endpoint

**Files:**
- Modify: `backend/app/blueprints/api/migration_api.py`
- Modify: `tests/unit/test_migration_api.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_migration_api.py`:

```python
class TestMigrationExecute:
    """Tests for POST /api/migration/execute"""

    @patch('backend.app.blueprints.api.migration_api.InventoryService')
    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_execute_creates_inventory_items(self, MockTrading, MockInventory, client):
        """Should create inventory item + offer for each listing ID"""
        # Mock Trading API to return listing details
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '111', 'title': 'Item A', 'price': 19.99, 'sku': '', 'imageUrl': 'http://img.jpg',
                 'condition': 'Used', 'availableQuantity': 1},
            ]
        }, 200)

        # Mock Inventory API calls
        mock_inv = MockInventory.return_value
        mock_inv.create_inventory_item.return_value = ({'success': True}, 200)
        mock_inv.create_offer.return_value = ({'success': True, 'offerId': 'offer123'}, 200)

        resp = client.post('/api/migration/execute', json={'listingIds': ['111']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['responses']) == 1
        assert data['responses'][0]['statusCode'] == 200

    def test_execute_rejects_empty_list(self, client):
        """Should 400 when no listing IDs provided"""
        resp = client.post('/api/migration/execute', json={'listingIds': []})
        assert resp.status_code == 400

    @patch('backend.app.blueprints.api.migration_api.InventoryService')
    @patch('backend.app.blueprints.api.migration_api.TradingService')
    def test_execute_reports_failures(self, MockTrading, MockInventory, client):
        """Should report failure when inventory creation fails"""
        mock_ts = MockTrading.return_value
        mock_ts.get_active_listings_light.return_value = ({
            'listings': [
                {'listingId': '999', 'title': 'Bad Item', 'price': 5.00, 'sku': '', 'imageUrl': None,
                 'condition': 'Used', 'availableQuantity': 1},
            ]
        }, 200)

        mock_inv = MockInventory.return_value
        mock_inv.create_inventory_item.return_value = ({'error': 'Create failed'}, 500)

        resp = client.post('/api/migration/execute', json={'listingIds': ['999']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['responses'][0]['statusCode'] == 500
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_migration_api.py::TestMigrationExecute -v`
Expected: FAIL with 404 (route doesn't exist yet)

**Step 3: Add the execute endpoint**

Append to `backend/app/blueprints/api/migration_api.py`:

```python
@migration_bp.route('/migration/execute', methods=['POST'])
def execute_migration():
    """
    Import selected eBay listings into the Inventory API.

    Accepts: { listingIds: string[] }
    Returns: { responses: [{ listingId, statusCode, error? }] }
    """
    try:
        data = request.get_json()
        listing_ids = data.get('listingIds', [])

        if not listing_ids:
            return error_response('No listing IDs provided', 400)

        # Fetch current eBay listings to get full details
        trading = TradingService()
        result, status = trading.get_active_listings_light()

        if status != 200:
            return error_response('Failed to fetch listing details from eBay', 502)

        # Build lookup by listing ID
        listings_by_id = {
            l['listingId']: l for l in result.get('listings', [])
        }

        inventory = InventoryService()
        env = load_env()
        responses = []

        for lid in listing_ids:
            listing = listings_by_id.get(lid)
            if not listing:
                responses.append({
                    'listingId': lid,
                    'statusCode': 404,
                    'error': 'Listing not found on eBay'
                })
                continue

            try:
                # Generate SKU if not present
                import hashlib
                sku = listing.get('sku') or ''
                if not sku or not sku.startswith('DC-'):
                    sku = f"DC-{hashlib.md5(lid.encode()).hexdigest()[:8].upper()}"

                # Create inventory item
                item_payload = {
                    'product': {
                        'title': listing.get('title', 'Untitled'),
                        'imageUrls': [listing['imageUrl']] if listing.get('imageUrl') else [],
                    },
                    'condition': listing.get('condition', 'USED_EXCELLENT'),
                    'availability': {
                        'shipToLocationAvailability': {
                            'quantity': listing.get('availableQuantity', 1)
                        }
                    }
                }

                res, code = inventory.create_inventory_item(sku, item_payload)
                if code not in (200, 204):
                    responses.append({
                        'listingId': lid,
                        'statusCode': code,
                        'error': res.get('error', 'Failed to create inventory item')
                    })
                    continue

                # Create offer linking to existing listing
                offer_payload = {
                    'sku': sku,
                    'marketplaceId': 'EBAY_US',
                    'format': 'FIXED_PRICE',
                    'listingDescription': listing.get('title', ''),
                    'pricingSummary': {
                        'price': {
                            'value': str(listing.get('price', 0)),
                            'currency': 'USD'
                        }
                    },
                    'availableQuantity': listing.get('availableQuantity', 1),
                    'listingPolicies': {
                        'fulfillmentPolicyId': env.get('EBAY_FULFILLMENT_POLICY', ''),
                        'paymentPolicyId': env.get('EBAY_PAYMENT_POLICY', ''),
                        'returnPolicyId': env.get('EBAY_RETURN_POLICY', ''),
                    },
                    'merchantLocationKey': env.get('EBAY_MERCHANT_LOCATION', ''),
                }

                offer_res, offer_code = inventory.create_offer(offer_payload)
                if offer_code in (200, 201):
                    responses.append({'listingId': lid, 'statusCode': 200})
                else:
                    # Item created but offer failed — still partial success
                    responses.append({
                        'listingId': lid,
                        'statusCode': offer_code,
                        'error': offer_res.get('error', 'Failed to create offer')
                    })

            except Exception as e:
                logger.error(f"Migration failed for listing {lid}: {e}")
                responses.append({
                    'listingId': lid,
                    'statusCode': 500,
                    'error': str(e)
                })

        return jsonify({'responses': responses}), 200

    except Exception as e:
        logger.exception("Migration execute failed")
        return error_response(str(e))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_migration_api.py -v`
Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add backend/app/blueprints/api/migration_api.py tests/unit/test_migration_api.py
git commit -m "feat: add /api/migration/execute endpoint for legacy listing import"
```

---

### Task 3: Build frontend, verify end-to-end, final commit

**Files:**
- None new — just build + verify

**Step 1: Run full unit test suite**

Run: `pytest tests/unit/ -v`
Expected: All tests pass (existing + 6 new)

**Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Clean build, no errors

**Step 3: Manual smoke test**

1. Start backend: `python backend/wsgi.py`
2. Open `http://localhost:5000/app/`
3. Navigate to Inventory tab
4. Click "Import Legacy Listings"
5. Verify: spinner shows → items load → no "Scan failed" error
6. Items with existing local jobs show "Synced" badge

**Step 4: Commit build output**

```bash
git add static/app/
git commit -m "build: rebuild frontend with migration API support"
```

---

## Verification Checklist

- [ ] `GET /api/migration/check` returns items with `inInventory` flag
- [ ] `GET /api/migration/check` handles Trading API errors gracefully (502)
- [ ] `GET /api/migration/check` returns empty array when no listings (not error)
- [ ] `POST /api/migration/execute` creates inventory items via REST API
- [ ] `POST /api/migration/execute` rejects empty listing IDs (400)
- [ ] `POST /api/migration/execute` reports per-item failures
- [ ] MigrationModal loads without "Scan failed" error
- [ ] All existing tests still pass
