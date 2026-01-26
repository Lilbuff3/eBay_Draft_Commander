# Smart Pricing & SDK Migration

- [x] Smart Pricing (Feature 3)
    - [x] Update `PricingEngine` (Condition Multipliers, Margin Logic)
    - [x] Update `create_research_draft.py` (Args, Profit Output)
    - [x] Create & Run `scripts/test_smart_pricing.py`
- [x] SDK Migration
    - [x] Migrate `ai_analyzer.py` to `google-genai`
    - [x] Create & Run `scripts/test_ai_analyzer_v2.py`
- [x] Verification
    - [x] Run End-to-End Test (`create_research_draft.py` with `acquisition_cost`)

# Book Listing Automation
- [ ] Requirements Gathering
    - [ ] Review `planning/book_listing_plan.md`
    - [ ] Decide on ISBN detection method (AI vs Local)
- [ ] Implementation (Phase 1)
    - [ ] Prototype ISBN Extractor (`scripts/test_isbn.py`)
    - [ ] Create `BookService` (`backend/app/services/book_service.py`)
    - [ ] Create `create_book_draft.py`
