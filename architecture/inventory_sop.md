# SOP: Inventory API Draft Creation

## Purpose
To create "Draft" listings on eBay using the modern Inventory API. This replaces the legacy Trading API `AddFixedPriceItem` flow.

## The 2-Step Process

In the Inventory API, a "listing" is composed of two distinct entities:

1.  **Inventory Item** (`PUT /sell/inventory/v1/inventory_item/{sku}`)
    - Represents the *physical product*.
    - Contains: Title, Description, Images, Aspects (Brand, MPN), Shipping Quantity.
    - **Note**: Does NOT contain Price, Shipping Policy, or Payment Policy.

2.  **Offer** (`POST /sell/inventory/v1/offer`)
    - Represents the *terms of sale*.
    - Contains: Price, Policies (Shipping/Payment/Return), Marketplace (US), and the Link to the SKU.
    - **State**: Can be `DRAFT` (unpublished) or `PUBLISHED` (live).

## Logic Flow

1.  **Prepare Product Data**:
    - Construct the JSON payload for the Inventory Item.
    - Ensure `product.description` is HTML formatted.
    - **Critical**: `condition` must be one of the allowed enums (e.g., `USED_EXCELLENT`).

2.  **Upsert Inventory Item**:
    - Call `PUT /inventory_item/{sku}`.
    - This is idempotent. If it exists, it updates.

3.  **Prepare Offer Data**:
    - Construct the JSON payload for the Offer.
    - **Critical**: Must include valid `listingPolicies` IDs (Shipping/Payment/Return) fetched from the User's Account Policy cache.

4.  **Create Offer**:
    - Call `POST /offer`.
    - **Result**: Returns an `offerId`.
    - At this point, the item is a **DRAFT** visible in Seller Hub "Inventory" tab (and often "Drafts" tab depending on view).

## Error Handling
- **400 Bad Request**: usually invalid JSON or missing required fields (like `aspects`).
- **401 Unauthorized**: Token expired. Refresh and retry.
- **409 Conflict**: Offer already exists for this SKU (sometimes happens).
