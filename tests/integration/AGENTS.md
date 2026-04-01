<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# integration

## Purpose
Full end-to-end pipeline tests with real eBay sandbox APIs, real Gemini vision analysis, and real fixture images. Tests complete flow from image upload → AI analysis → category → pricing → eBay Trading API. Creates actual scheduled listings (20 days out on sandbox).

## Key Files

| File | Description |
|------|-------------|
| `test_full_pipeline.py` | Complete flow: image → Gemini analysis → category → pricing → Trading API AddFixedPriceItem. Uses all 3 fixture sets (boombox, cookbook, tesla-jacket). Includes `cleanup` task to end listings. ~11s per fixture. |
| `test_live_pipeline.py` | Quick API-only variant — minimal Gemini calls, focuses on Trading API cycle and response validation. ~9s. |
| `test_trading_api.py` | XML request/response validation, AddFixedPriceItem format, ScheduleTime handling |
| `test_schedule.py` | Scheduled listing creation (20 days future) and datetime validation |
| `test_smart_pricing.py` | Full pricing engine with real market research and comp analysis |
| `test_ebay_offers.py` | eBay Offers API response validation |
| `test_beta_listing_api.py` | Inventory API variant and format testing |
| `test_xml_sanitization.py` | XML escaping in descriptions, HTML safety for eBay display |

## For AI Agents

### Working In This Directory
- **Requires .env credentials**: `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_USER_TOKEN`, `GOOGLE_API_KEY`, `EBAY_BUSINESS_POLICY_SHIPPING`, `EBAY_BUSINESS_POLICY_PAYMENT`, `EBAY_BUSINESS_POLICY_RETURN`
- **Creates real listings on eBay sandbox** — scheduled 20 days out. Do not run casually.
- Run all: `pytest tests/integration/ -v -s` (slow)
- Run by fixture: `pytest tests/integration/test_full_pipeline.py -k "cookbook" -v -s`
- **Cleanup after runs**: `pytest tests/integration/test_full_pipeline.py -k "cleanup" -v -s`
- Fixture images at `tests/fixtures/images/{boombox,cookbook,tesla-jacket}/` (do not edit)
- Created listing IDs tracked in `tests/fixtures/_test_listings.json` for tracking and cleanup

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
