# Book Listing Automation — Implementation Plan

## Overview
Wire existing pieces together so book listings created via ISBN scan flow through the queue processor correctly, bypassing unnecessary AI vision analysis and using pre-populated metadata.

## What Already Works
- `ISBNScanner.scan_image()` — Gemini Vision ISBN extraction (standalone)
- `BookService.lookup_isbn()` — Google Books API (standalone)
- `GET /api/lookup/book` — Full lookup endpoint with pricing
- `POST /api/jobs/create-from-metadata` — Creates queue jobs from metadata
- `ScannerModal` — Manual ISBN entry, creates real jobs via api.ts
- `BatchScan` page — Hardware scanner UI, table view, BUT Draft All is a stub
- `PricingEngine` — Strategy 1 already supports ISBN-first pricing

## What's Broken/Missing
1. `frontend/src/lib/api.ts` does not exist — 5 files import it, frontend can't build
2. `BatchScan.handleDraftAll()` is a stub (simulates with setTimeout)
3. `ProcessorService.create_listing()` ignores book metadata — always runs full AI analysis
4. No `listing_type: 'book'` tag in job metadata
5. `ScannerListener.tsx` hardcodes `http://localhost:5000`
6. Condition values in BatchScan don't map to eBay condition enums

---

## Task 1: Create `frontend/src/lib/api.ts`
**Why:** Critical blocker. 5 components import from this file but it doesn't exist.

**File:** `frontend/src/lib/api.ts`

Create the API client module exporting all functions/types currently imported:
- From `App.tsx`: `fetchJobs`, `fetchStatus`, `startQueue`, `pauseQueue`, `scanInbox`, `Job` type, `QueueStats` type
- From `Dashboard.tsx`: `createListing`, `Job`, `QueueStats`, `addFolderToQueue`, `fetchJobDetails`, `JobDetails` type
- From `Settings.tsx`: `getSettings`, `saveSettings`
- From `QueueCard.tsx`: `Job` type, `JobStatus` type
- From `ScannerModal.tsx`: `lookupBook`, `createJobFromMetadata`

Use relative fetch to `/api/...` (not hardcoded localhost).

**Verification:** `cd frontend && npx tsc --noEmit` (or grep for import errors)

---

## Task 2: Fix `BatchScan.handleDraftAll()` — Wire to Real API
**Why:** The "Draft All" button is the core book workflow and currently does nothing.

**File:** `frontend/src/pages/BatchScan.tsx`

Changes:
1. Import `createJobFromMetadata` from `@/lib/api`
2. Replace the `setTimeout` stub in `handleDraftAll()` with real API calls
3. For each valid item, call `createJobFromMetadata()` with:
   ```ts
   {
     title: item.fullData.title,
     isbn: item.isbn,
     description: item.fullData.description,
     price: item.price,
     condition: item.condition,
     stock_photo: item.stock_photo,
     item_specifics: item.fullData.item_specifics,
     listing_type: 'book',
     source_data: item.fullData
   }
   ```
4. Fix hardcoded `http://localhost:5000` in `handleScan()` to use relative `/api/lookup/book`

**Verification:** Manual — scan an ISBN, verify job appears in queue

---

## Task 3: Update `POST /api/jobs/create-from-metadata` to Tag Book Jobs
**Why:** Processor needs to know this is a book job to skip AI analysis.

**File:** `backend/app/blueprints/api.py` (the `create-from-metadata` endpoint)

Changes:
1. Extract `listing_type` from request body and store it in `job_metadata`
2. Store `isbn`, `item_specifics`, `price`, `condition` in the job's metadata dict
3. Pre-populate `user_title`, `user_price`, `user_condition` on the QueueJob so the processor respects them
4. Map friendly condition strings ("Like New", "Very Good", etc.) to eBay enums using `CONDITION_MAP` or `validate_condition()`

**Verification:** `pytest tests/test_business_logic.py -v`

---

## Task 4: Add Book-Aware Path in `ProcessorService.create_listing()`
**Why:** Book jobs have all data pre-populated. Running full AI vision analysis on a cover photo is slow and wasteful.

**File:** `backend/app/services/processor_service.py`

Changes:
1. At the top of `create_listing()`, after folder validation, check:
   ```python
   is_book = job_obj.job_metadata.get('listing_type') == 'book'
   ```
2. If `is_book` and job already has `ai_data` populated (from metadata):
   - Skip `_perform_enhanced_ai_analysis()` — use pre-populated data
   - Use hardcoded book category ID `"267"` (skip `CategoryMapper`)
   - Pass `isbn` from `job_metadata` to `_determine_final_pricing()` so it uses Strategy 1
   - Use pre-populated `item_specifics` from metadata
3. Rest of pipeline (image upload, template rendering, eBay bundle) runs as normal

**Verification:** `pytest tests/test_business_logic.py tests/test_condition_logic.py -v`

---

## Task 5: Add Book-Specific Test
**Why:** Validate the book bypass path works correctly.

**File:** `tests/test_book_listing.py` (new)

Test cases:
1. `test_book_listing_skips_ai_analysis` — Create a QueueJob with `listing_type: 'book'` and pre-populated ai_data. Assert `ai.analyze_with_research` is NOT called.
2. `test_book_listing_uses_isbn_pricing` — Assert pricing engine receives `isbn` parameter.
3. `test_book_listing_uses_book_category` — Assert category ID is `"267"` (not from CategoryMapper).

**Verification:** `pytest tests/test_book_listing.py -v`

---

## Task 6: Fix `ScannerListener.tsx` Hardcoded URL
**Why:** Currently hardcodes `http://localhost:5000`, breaks in production.

**File:** `frontend/src/components/ScannerListener.tsx`

Change: Replace `http://localhost:5000/api/lookup/book` with `/api/lookup/book`

**Verification:** Grep for `localhost:5000` in frontend — should return 0 results

---

## Execution Order
Batch 1 (Tasks 1-3): API client + wiring
Batch 2 (Tasks 4-6): Processor logic + tests + cleanup

## Not In Scope (Future)
- Camera-based ISBN capture (mobile companion)
- Dynamic book category mapping (Fiction/Non-Fiction/Textbooks)
- ISBN checksum validation
- `isbn` DB column (currently in metadata JSON — fine for now)
- Media Mail auto-selection for shipping policy
