<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# tests

## Purpose
Test suite: 32+ unit test files (244+ assertions), 8 integration tests with real eBay sandbox APIs, manual verification scripts. Pytest for backend, Vitest for frontend.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `unit/` | Fast isolated unit tests (32 files, ~244 assertions, <30s). No API calls; all dependencies mocked. See `unit/AGENTS.md` |
| `integration/` | Full pipeline tests with real eBay sandbox + Gemini. Creates actual scheduled listings. See `integration/AGENTS.md` |
| `manual/` | Ad-hoc verification scripts (e2e, system health, phase completion checks). Run with `python`, not pytest. |
| `fixtures/` | Test data — real product images (boombox, cookbook, tesla-jacket) for pipeline testing. See `fixtures/AGENTS.md` |

## For AI Agents

### Working In This Directory
- Run unit tests: `pytest tests/unit/ -v` (~30s, no credentials needed)
- Run integration tests: `pytest tests/integration/ -v -s` (slow, requires .env with EBAY_APP_ID, EBAY_CERT_ID, EBAY_USER_TOKEN, GOOGLE_API_KEY)
- Integration tests create real scheduled listings on eBay sandbox (20 days out)
- Cleanup integration tests: `pytest tests/integration/test_full_pipeline.py -k "cleanup" -v -s`
- See CLAUDE.md for full test commands and environment setup

### Conventions
- Files: `test_*.py`, classes: `Test*`, functions: `test_*`
- Mock external services with `unittest.mock.patch` and `MagicMock`
- Fixture images at `tests/fixtures/images/{boombox,cookbook,tesla-jacket}/` (do not edit)
- Track created listing IDs in `tests/fixtures/_test_listings.json` for cleanup

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
