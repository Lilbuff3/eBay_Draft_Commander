<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# services

## Purpose
Business logic layer. Orchestrates AI analysis, eBay integration, pricing, image processing, queue management, and end-to-end listing creation pipeline.

## Key Files

| File | Description |
|------|-------------|
| `listing_ai_agent.py` | AI listing orchestrator — coordinates vision analysis, web research, pricing, category mapping, template rendering |
| `processor_service.py` | Main pipeline — condition validation, AI analysis, category mapping, pricing, images, eBay submission |
| `queue_manager.py` | Job lifecycle management, background processing thread, Socket.IO event hub, pause/resume/skip logic |
| `queue_job.py` | JobStatus enum, QueueJob dataclass, thumbnail resolution constants |
| `ai_analyzer.py` | Gemini 2.0 Flash Phase 1 (vision) + Phase 2 (web research grounding) |
| `ai_price.py` | Gemini-based price estimation fallback when market data insufficient |
| `pricing_engine.py` | Market pricing cascade: ISBN → MPN → keywords → web research → AI estimate |
| `category_mapper.py` | AI-to-eBay category mapping with taxonomy validation and printer parts guard |
| `ebay_service.py` | High-level eBay facade — search, preview, publish, withdraw, fetch active |
| `image_processor.py` | Image validation, resize, background removal via rembg, eBay upload coordination |
| `image_service.py` | Image upload coordination and cache management |
| `template_manager.py` | HTML description rendering with inline styles (no external CSS) |
| `item_specifics_mapper.py` | eBay aspect mapping with fuzzy matching, auto-fills "Does Not Apply" for SAFE_DEFAULT_ASPECTS |
| `scanner_service.py` | Inbox folder scanning, job creation from image files |
| `isbn_scanner.py` | ISBN barcode detection from images via Gemini vision |
| `book_service.py` | Book metadata lookup: ISBN → title, author, edition, price |
| `category_correction_cache.py` | User feedback cache to prevent repeat miscategorizations |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `ebay/` | eBay REST/XML API modules (see `ebay/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Services are stateless — persistence via core layer (models, settings, tokens)
- Pipeline stages cache results in `job.ai_json` to avoid re-computation
- Use `NeedsReviewException` when job needs manual review — routes to review, not failure
- Use `get_logger(__name__)` + optional `log_callback` for Socket.IO UI updates
- Check `RateLimiter.try_acquire()` before Gemini/eBay API calls
- Services emit Socket.IO events for real-time UI sync (never routes)

### Key Patterns
- **Rate limiting**: Call `RateLimiter.try_acquire('gemini')` before Gemini, `RateLimiter.try_acquire('ebay')` before eBay
- **Logging**: `logger.info("message"); log_callback(f"update: {status}")` for UI sync
- **Caching**: Store intermediate results in `job.ai_json` (JSON string) to avoid re-processing
- **Exceptions**: Raise `DraftCommanderError`, `eBayAPIError`, or `NeedsReviewException` for caller handling
- **Pricing cascade**: ISBN → MPN → keywords → research → AI, with fallback strategy
- **Condition chain**: user_override > metadata > folder_name > AI > DEFAULT
- **Aspects**: Auto-fill SAFE_DEFAULT_ASPECTS with "Does Not Apply", validate with taxonomy

### Exception Handling
- `DraftCommanderError` — app-level error, user sees friendly message
- `eBayAPIError` — eBay API failure, retry logic in calling code
- `NeedsReviewException` — job stalled, needs human review, routes to review queue

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
