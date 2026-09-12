<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# tools

## Purpose
Command-line utility scripts for debugging, eBay API operations, inventory management, and manual listing workflows. Direct access to eBay APIs, database operations, and queue management for one-off tasks, testing, and troubleshooting.

## Key Files
| File | Description |
|------|-------------|
| `inventory_sync.py` | Sync active eBay listings locally via Trading API GetSellerList or Inventory API (feeds migration/import workflow) |
| `queue_logger.py` | Query and analyze job queue state, log job events, outcomes, error tracking |
| `get_policies.py` | Fetch and validate eBay business policies (fulfillment, payment, return) |
| `update_policies.py` | Update policy IDs in .env from eBay API (automated credential sync) |
| `get_aspects.py` | Fetch item specifics schema (aspects) for a category ID from Taxonomy API |
| `find_category.py` | Query eBay Taxonomy API to find correct category ID for a product |
| `end_listing.py` | End/cancel active eBay listing by item ID |
| `exchange_token.py` | Refresh eBay OAuth token (manual credential renewal) |
| `inspect_db_schema.py` | Inspect SQLite database schema and table structure (debug tool) |
| `inspect_queue.py` | Print current job queue state (pending, processing, completed, failed) |
| `run_queue_now.py` | Manually trigger queue processing (equivalent to QueueService.start_processing()) |
| `read_last_error.py` | Read and print last error from queue logs for debugging |
| `reset_and_cleanup.py` | Reset queue state and clean up orphaned media files |
| `debug_mcp.py` | Debug MCP (Model Context Protocol) server connectivity and diagnostics |

## Subdirectories
(None — all tools in root of tools/ directory)

## For AI Agents

### Working In This Directory
- Tools are CLI utilities, run via `python tools/<script>.py` from project root
- Most tools import from `backend.app` — ensure Flask app context available or imports loaded
- API tools (get_aspects, find_category, get_policies) call eBay REST/XML APIs directly
- Queue/job tools interact with SQLite database at `data/commander.db`
- Publishing tools use Trading API `AddFixedPriceItem` XML for eBay submission
- All tools load credentials from `.env` via `load_dotenv()` or environment variables
- Output printed to console; some tools may write JSON logs to `data/` directory
- **By design: read-only or testing tools** — no production data modified without explicit action

### Running Tools

```bash

# Check queue state
python tools/inspect_queue.py

# Fetch eBay policies
python tools/get_policies.py

# Sync inventory from eBay
python tools/inventory_sync.py --seller-list


# Cleanup and reset
python tools/reset_and_cleanup.py --dry-run
```

### Dependencies
- Tools import: `backend.app.services` (AI, pricing, eBay, queue, category), `backend.app.core` (models, constants, validators)
- Tools use: `backend.app.services.ebay.taxonomy`, `.trading`, `.inventory`, `.policies` modules
- Queue/job tools access: SQLite at `data/commander.db` (JobModel, TemplateModel tables)
- Publishing tools use: Trading API via `backend.app.services.ebay.trading.TradingAPIService`
- Preview generator uses: `backend.app.services.template_manager.TemplateManager.render_template()`
- Credentials: eBay token (EBAY_USER_TOKEN), App ID (EBAY_APP_ID), Cert ID (EBAY_CERT_ID), Gemini API key (GOOGLE_API_KEY)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
- All tools are **read-only or testing** by default
- Use `--dry-run` flags (if implemented) to preview changes before committing
- Publishing tools require valid .env credentials: EBAY_USER_TOKEN, EBAY_APP_ID, EBAY_CERT_ID, business policy IDs
- Database tools use SQLite — ensure `data/commander.db` exists before running
