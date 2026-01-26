# Smart Pricing & SDK Migration Plan

## Goal Description
1.  **Smart Pricing (Feature 3)**: Enhance `PricingEngine` to support acquisition cost (margin protection) and refined condition logic (NOS vs Used).
2.  **SDK Migration (Housekeeping)**: Migrate `ai_analyzer.py` from the deprecated `google-generativeai` package to the new `google-genai` SDK, unifying the codebase on the latest Google AI tools.

## User Review Required
> [!IMPORTANT]
> **Logic Assumption**: For Smart Pricing, I will assume "New Old Stock" (NOS) should be priced equivalent to "New - Open Box" (0.90 multiplier) unless "New" comps are found. I will also add a `min_margin` check (default $10 or 15%) to flag low-profit items.
>
> **Dependency**: This plan assumes `google-genai` library is installed or will be installed.

## Proposed Changes

### 1. Smart Pricing (Feature 3)

#### [MODIFY] [pricing_engine.py](file:///c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/backend/app/services/pricing_engine.py)
-   **Update `CONDITION_MULTIPLIERS`**: Explicitly add "New Old Stock" (0.90) and "New Other" (0.90).
-   **Update `calculate_suggested_price`**:
    -   Accept `acquisition_cost` (float, default 0.0).
    -   Calculate `estimated_ref_fees` (approx 13% + $0.30).
    -   Calculate `projected_profit`.
    -   Implement "Margin Protection": If `projected_profit` < `min_profit` (e.g. $10), suggest a higher price (`cost + fees + min_profit`).
    -   Return `margin_data` in the result.

#### [MODIFY] [create_research_draft.py](file:///c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/create_research_draft.py)
-   **Update args**: Add `acquisition_cost` argument to `create_research_draft`.
-   **Pass to Pricing**: Pass this cost to `analyze_with_research` -> `pricing_engine`.
-   **Display Profit**: Print projected profit summary in the console output.

### 2. Google SDK Migration (Housekeeping)

> [!WARNING]
> **Strict Migration**: The legacy `google-generativeai` package must be completely removed.

#### [MODIFY] [ai_analyzer.py](file:///c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/backend/app/services/ai_analyzer.py)
-   **Dependencies**: Uninstall `google-generativeai`, install `google-genai`.
-   **Imports**: Replace `import google.generativeai as genai` with `from google import genai`.
-   **Initialization**: 
    ```python
    from google import genai
    client = genai.Client(api_key=...)
    ```
-   **Generation**: 
    ```python
    client.models.generate_content(
        model='gemini-2.5-flash', 
        contents='...', 
        config=...
    )
    ```
-   **Search Grounding**: Use the built-in `tools=[{'google_search': {}}]` or types-based config from the new SDK.

#### [MODIFY] [pricing_engine.py](file:///c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/backend/app/services/pricing_engine.py)
-   **Update**: Ensure `PricingEngine` also uses the new `google-genai` SDK for its pricing grounding.

## Verification Plan

### Automated Tests
-   **Pricing Logic**: Create a script `scripts/test_smart_pricing.py` to unit test `PricingEngine`.
    -   Test Case 1: Item with ample margin.
    -   Test Case 2: Item with negative margin (verify protection logic).
    -   Test Case 3: NOS condition multiplier.
-   **SDK Migration**: Run `scripts/test_ai_analyzer_v2.py` (I will create this) to verify `AIAnalyzer` works with the new SDK.
    -   It should analyze a sample image and return JSON without errors.

### Manual Verification
-   **End-to-End**: Run `create_research_draft.py` on a new folder (I will create a dummy folder `test_item_nos`) with an `acquisition_cost`.
-   **Verify Output**: Check console for "Projected Profit" line and ensure price reflects the logic.
