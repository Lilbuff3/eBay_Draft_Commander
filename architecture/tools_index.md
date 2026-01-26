# Index of Tools and Scripts

This index documents every utility script moved to the `tools/` directory during the Phase A Architecture Backfill.

## Core Operations

| Script | Purpose | SOP Link |
|--------|---------|----------|
| `create_from_folder.py` | Main listing creation logic (Photos -> Listing) | [listing_logic.md](listing_logic.md) |
| `ebay_api.py` | Primary eBay REST API Client (OAuth, Taxonomy) | [ebay_api.md](ebay_api.md) |
| `inventory_sync.py` | Synchronizes local inventory state with eBay | [inventory_sync.md](inventory_sync.md) |
| `price_research.py` | Fetches sold comps for pricing intelligence | [price_research.md](price_research.md) |
| `photo_editor.py` | Headless image processing (brightness, crop, etc.) | [photo_editor.md](photo_editor.md) |

## Listing Utilities

- **`create_and_publish.py`**: Quick script to create an item and publish it in one shot.
- **`create_listing.py`**: Earlier version of listing logic, kept for compatibility testing.
- **`create_full_listing.py`**: Handles comprehensive listing creation with detailed specifics.
- **`create_research_draft.py`**: Creates a draft based solely on AI research without final photos.
- **`final_listing.py`**: Final step in the listing refinement process.
- **`publish_offer.py`**: Standalone tool to publish an existing eBay offer ID.
- **`try_publish.py`**: Automated retry logic for failed publishing attempts.
- **`smart_listing.py`**: Experimental version using advanced AI templates.

## eBay API Helpers

- **`ebay_complete.py`**: Helper to complete transaction/listing details.
- **`ebay_direct.py`**: Minimal wrapper for direct API calls bypassing the client class.
- **`ebay_listing.py`**: Model for eBay listing objects.
- **`ebay_orders.py`**: Fetches and processes recent order history for analytics.
- **`ebay_upload_trading.py`**: Legacy Trading API image uploader (Picture Services).
- **`exchange_token.py`**: Utility to exchange Auth Code for Refresh Tokens.
- **`find_category.py`**: Standalone category search utility.
- **`get_aspects.py`**: Standalone aspect retrieval utility.
- **`get_policies.py`**: Fetches Business Policy IDs (Shipping, Return, Payment) from eBay.

## System & Debug

- **`verify_system_health.py`**: Connectivity and environment check (Phase L).
- **`verify_server_auth.py`**: Validates current OAuth tokens and scopes.
- **`debug_env.py`**: Prints and validates environment variables.
- **`check_inv.py`**: Quick check of an item's availability on eBay by SKU.
- **`list_all.py` / `list_inventory.py`**: Lists all active listings in various formats.
- **`run_cletop.py`**: Runs a "Console Listing Editor & Task Optimizer" (CLETOP) session.
- **`auto_refresh.py`**: Background task to keep OAuth tokens fresh.

## Testing

- **`test_book_logic.py` / `test_book_pricing.py`**: Domain-specific tests for book listings.
- **`test_research_draft.py`**: Validates the research-to-draft flow.
- **`test_upload.py`**: Tests Media API image uploads.
- **`test_xerox.py`**: Domain-specific case test for Xerox parts.
- **`run_test_item.py`**: End-to-end test with a sample item folder.
