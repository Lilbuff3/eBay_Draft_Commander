<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# docs

## Purpose
Planning and design documentation for eBay Draft Commander features, architecture decisions, and implementation roadmaps. Plans are detailed specifications with task breakdowns, file lists, and acceptance criteria for developers.

## Key Files
| File | Description |
|------|-------------|
| `plans/2026-03-28-profit-optimization-features.md` | 6 profit optimization features: smart shipping tiers, Media Mail detection, profit calculator UI, comp filtering, price labels, scheduling presets |
| `plans/2026-03-21-wire-research-through-pipeline.md` | Web research integration: Gemini grounding, pricing comps, specs enrichment. 40+ new tests. |
| `plans/2026-03-20-migration-api.md` | Migration API: sync legacy eBay listings locally via GetSellerList integration |
| `plans/2026-03-19-pricing-and-specifics-accuracy.md` | Pricing engine improvements and aspect mapping validation for accuracy |
| `plans/2026-02-25-mobile-ux-redesign.md` | Mobile UI refinements for responsive listing creation workflow |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `plans/` | Implementation plan markdown files (one per feature sprint) |

## For AI Agents

### Working In This Directory
- Read plans **before implementing features** — they define task lists, file references, and acceptance criteria
- Plans use markdown with numbered task breakdowns (1-N) and file paths
- Cross-reference CLAUDE.md for architecture constraints (Trading API for new listings, Zustand store patterns, SQLite database)
- When writing a plan: include Files section (exact relative paths), numbered Task sections, Tech Stack summary, and Acceptance Criteria
- Link to AGENTS.md files for navigation context

### Plan Structure (Example)
```
## Files to Create/Modify
- backend/app/services/new_service.py
- tests/unit/test_new_service.py
- frontend/src/hooks/useNewFeature.ts

## Tasks
1. Create service class with core logic
2. Add unit tests (mock external APIs)
3. Integrate with ProcessorService pipeline
...
```

### Dependencies
- Plans reference backend services in `backend/app/services/` and frontend components in `frontend/src/`
- Plans reference database models in `backend/app/core/database.py`
- Plans assume familiarity with CLAUDE.md architecture section and existing codebase

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
