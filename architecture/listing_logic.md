# SOP: Listing Logic (`create_from_folder.py`)

## Purpose
This script provides the end-to-end engine for converting a folder of images into a live eBay listing or draft. It coordinates AI analysis, marketplace research, image hosting, and the eBay Inventory API.

## Location
`tools/create_from_folder.py`

## Workflow

### 1. Inbox Scanning
- Scans a directory for subdirectories (each represents one item).
- Validates that images exist within the subdirectory.

### 2. AI Enrichment (`AIAnalyzer`)
- Sends images to Google Gemini via `backend/app/services/ai_analyzer.py`.
- Extracts: `title`, `description`, `item_specifics`, and a baseline `suggested_price`.

### 3. Market Pricing (`PricingEngine`)
- Uses `backend/app/services/pricing_engine.py` to fetch "Sold" comps from eBay via the Browse API.
- Reconciles AI price with actual market data to produce a `final_price`.

### 4. Category & Aspects
- Uses `get_category_and_aspects` (SOP: `ebay_api.md`) to determine the eBay category ID.
- Maps AI extracts to **required** eBay aspects (e.g., MPN, Brand).

### 5. Media Upload
- Uploads images to eBay Picture Services (Media API).
- Fallback: Uses a placeholder if upload fails.

### 6. Inventory Creation
- Creates an **Inventory Item** (SKU-based) via `PUT /inventory_item/{sku}`.
- Creates an **Offer** (pricing + policies) via `POST /offer`.
- Key Requirement: Requires `EBAY_FULFILLMENT_POLICY`, `EBAY_PAYMENT_POLICY`, and `EBAY_RETURN_POLICY` IDs in `.env`.

### 7. Publishing
- Publishes the listing via `POST /offer/{offer_id}/publish`.
- If `AUTO_PUBLISH` is `false`, it remains as a draft in eBay.

## Usage
```python
from tools.create_from_folder import create_listing_from_folder

# Single folder processing
create_listing_from_folder("inbox/camera_kit", price="199.99")
```

## Dependencies
- `backend.app.services`: For AI and Pricing modules.
- `.env`: For Policy IDs and User Tokens.
