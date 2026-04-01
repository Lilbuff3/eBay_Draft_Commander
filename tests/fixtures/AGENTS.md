<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# fixtures

## Purpose
Test data for integration pipeline testing. Real product photos (golden data) used by test_full_pipeline.py and test_live_pipeline.py. No code — images only.

## Key Files and Directories

| Item | Description |
|------|-------------|
| `images/boombox/` | Aiwa CSD-ES227 stereo (10 JPEG photos) — electronics category test fixture |
| `images/cookbook/` | Coffee cookbook with ISBN barcode visible (4 JPEG photos) — books category test fixture |
| `images/tesla-jacket/` | Tesla branded jacket (4 JPEG photos) — apparel category test fixture |
| `_temp_inbox/` | (generated during runs) Temporary image copies — safe to delete |
| `_test_listings.json` | (generated during runs) Tracks created listing IDs, used by cleanup task |

## For AI Agents

### Working In This Directory
- **Do not edit fixture images** — these are golden test data; changes break test reproducibility
- Add new fixtures: create `images/{product-name}/` directory with 4-10 valid JPEGs
- Access in tests: `FIXTURES_DIR = PROJECT_ROOT / 'tests' / 'fixtures' / 'images'`
- Generated files (`_temp_inbox/`, `_test_listings.json`) can be safely deleted to reset test state
- Images must be: valid JPEG format, loadable by Python Pillow, min resolution ~480x480px

### Test Usage
- `test_full_pipeline.py` uses all 3 fixture sets in parameterized tests
- `test_live_pipeline.py` also uses these fixtures for API-only flow testing
- Listing IDs from runs stored in `_test_listings.json` for test cleanup

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
