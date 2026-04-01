<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# unit

## Purpose
Fast isolated unit tests — 32 files, ~244+ assertions, <30 seconds. No external API calls; all dependencies mocked with unittest.mock. Tests core business logic, validation, pricing, categorization, and security.

## Key Files

| File | Description |
|------|-------------|
| `test_validation.py` | Input validation (price, title, ISBN, condition mapping) |
| `test_pricing_engine.py` | Condition multipliers, comp analysis, rarity-aware pricing logic |
| `test_category_taxonomy.py` | Category mapping, guard rails, condition validation |
| `test_item_specifics.py` | Aspect truncation (65 chars max), value cleaning, matching |
| `test_research_pricing.py` | Research-enriched pricing cascade and comp integration |
| `test_research_description.py` | Research data injection into HTML descriptions, XSS safety checks |
| `test_title_selection.py` | Title selection logic (SEO vs suggested, length priority) |
| `test_business_logic.py` | ProcessorService condition mapping, aspect cleaning |
| `test_condition_logic.py` | Condition priority chain and inference |
| `test_ai_refinement.py` | Gemini condition refinement when no explicit override |
| `test_ai_validation.py` | Confidence scoring and threshold enforcement |
| `test_config_consistency.py` | .env loading, policy defaults, configuration validation |
| `test_token_manager.py` | eBay token refresh, expiry handling, cache logic |
| `test_rate_limiter.py` | Token-bucket rate limiting for API calls |
| `test_queue_manager.py` | Job lifecycle, status transitions, persistence |
| `test_image_processor.py` | Image validation, JPEG format checks, background removal |
| `test_migration_api.py` | Legacy listing import, schema mapping, data conversion |
| `test_security.py` | Input sanitization, XSS prevention, path traversal protection |
| `test_shipping_estimation_unit.py` | Shipping cost estimation algorithms |
| `test_shipping_integration.py` | Category-aware shipping recalculation |
| `test_analytics_service.py` | Analytics and metrics tracking |
| `test_batch_approve.py` | Batch approval workflow and processing |
| `test_bulk_ops.py` | Bulk operations on multiple listings |
| `test_gemini_rpm_config.py` | Gemini API rate limit (RPM) configuration |
| `test_image_cache.py` | Image caching mechanisms and invalidation |
| `test_job_details_api.py` | Job detail API responses and serialization |
| `test_pipeline_split.py` | Pipeline phase splitting and routing |
| `test_queue_manager_cleanup.py` | Queue cleanup and orphaned job handling |
| `test_refactored_services.py` | Refactored service integration tests |
| `test_scan_api.py` | Image scanning and analysis API |

## For AI Agents

### Working In This Directory
- Run all: `pytest tests/unit/ -v`
- Run one file: `pytest tests/unit/test_validation.py -v`
- Run one test: `pytest tests/unit/test_validation.py::test_price_validation -v`
- Mock pattern: `from unittest.mock import patch, MagicMock`
- Env vars: `monkeypatch.setenv("KEY", "value")`
- Use `tmp_path` fixture for temporary files instead of real filesystem
- No credentials needed — all external services are mocked

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
