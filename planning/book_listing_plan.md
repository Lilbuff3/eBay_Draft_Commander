# Book Listing Automation Plan

## Goal
Extend "eBay Draft Commander" to specialized in listing books. The current industrial/NOS workflow is too generic. Book listing requires speed, ISBN scanning, and specific metadata (Author, Publisher, Year).

## Core Strategy
Pivot from "Search & Guess" (Industrial) to "Scan & Look up" (Books).

### 1. Detection Strategy (The "Trigger")
-   **Primary**: **ISBN Barcode**. Detection via AI Vision (Gemini 2.0 Flash is excellent at barcode/text reading) or a local library like `pyzbar` for speed.
-   **Fallback**: OCR of title/author from cover if no ISBN found (Vintage/Antique books).

### 2. Data Source (The "Enrichment")
-   **eBay Catalog API**: eBay has a massive catalog for books. Searching by ISBN returns stock photos, pre-filled Item Specifics, and weight/dim estimates.
-   **Google Books API**: Good fallback for metadata (description, page count).

### 3. Workflow Adaptation

#### Current Industrial Flow:
`Photo -> AI Identify -> Grounding Research -> Draft`

#### Proposed Book Flow:
`Photo (Back Cover) -> Extract ISBN -> Catalog Match -> Condition Grading -> Draft (Media Mail)`

## Proposed Implementation

### A. Backend Changes

1.  **Enhance `AIAnalyzer`**:
    -   Add `extract_isbn(image_path)` method.
    -   Prompt Gemini specifically to "Read the ISBN-13 or ISBN-10 barcode".

2.  **New Service: `BookService`**:
    -   `lookup_by_isbn(isbn)`: Calls eBay Catalog API / Browse API.
    -   Returns: Title, Author, Publisher, Year, Stock Photo URL.

3.  **Smart Pricing for Books**:
    -   Books rely heavily on "lowest price" competition.
    -   Update `PricingEngine` to search ISBN matches and find the *floor price*.

### B. Frontend Changes

1.  **"Book Mode" Toggle**:
    -   In `NewListing.tsx`, add a toggle or tab for "Book/Media".
    -   When active, minimal fields shown (Condition, ISBN, Price).

2.  **Barcode Scanner (Optional)**:
    -   Future: Allow mobile phone companion to scan barcode directly.

### C. Shipping

-   **Media Mail Default**:
    -   Logic to automatically select "USPS Media Mail" policy when category is "Books".

## Roadmap

- [ ] **Step 1: Prototype ISBN Extractor**
    -   Test Gemini 2.0 Flash on book back covers.
- [ ] **Step 2: Catalog Integration**
    -   Script to fetch book details from eBay Browse API using GTIN (ISBN).
- [ ] **Step 3: Book Draft Creator**
    -   `create_book_draft.py` (simplified version of `create_research_draft.py`).
- [ ] **Step 4: UI Integration**
    -   Add "Scan Book" button to Dashboard.

## Questions for User
-   Do you have a physical barcode scanner (USB), or do you want to rely purely on photos?
-   Are you focusing on modern books (ISBN) or antique books (No ISBN)?
