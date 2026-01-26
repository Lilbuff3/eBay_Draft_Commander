# Project Constitution: eBay Draft Commander Pro

> **Source of Truth**: "A complete solution for automating eBay listing creation using AI-powered image analysis and the modern eBay Inventory API."

## The North Star
The primary goal is to provide a seamless, AI-driven workflow for eBay sellers to go from physical photos to **eBay Drafts** (Unpublished Offers) with minimal manual effort.
**Key Requirement**: Use the **Inventory API** (not legacy Trading API) for modern compatibility.

## Source of Truth (Data Locations)
- **API Credentials**: Secured in `.env` (EBAY_APP_ID, EBAY_CERT_ID, EBAY_RU_NAME, GOOGLE_API_KEY).
- **Listing Data**: JSON objects stored locally in `inbox/` (raw) and `ready/` (processed).
- **Persistent State**:
  - `data/queue_state.json`: Status of the listing queue.
  - `data/templates.json`: Listing presets/templates (Must include Mobile-Friendly HTML).
  - `data/inventory_map.json`: Mapping of Local SKU -> eBay SKU -> Offer ID.

## Delivery Payload
**Target**: An **eBay Draft**.
In Inventory API terms, this means:
1.  **Inventory Item**: Created via `PUT /sell/inventory/v1/inventory_item/{sku}`.
2.  **Offer**: Created via `POST /sell/inventory/v1/offer` (State: `DRAFT`).
*Note: We do NOT strictly publish immediately. We create the draft for user review.*

## Behavioral Rules (The "Code of Conduct")
1.  **Mobile-First Design**: All HTML templates generated MUST render perfectly on mobile devices. No horizontal scrolling, legible fonts.
2.  **Professional Aesthetics**: Listings must use a "Professional" template that presents a high-quality brand image.
3.  **Precision Categorization**: The system must ensure all item categories are filled out correctly and the *most specific* category ID is selected using eBay's Taxonomy API.
4.  **Data-First Integrity**: Never guess. If specific item aspects are missing, flag them rather than inventing data.

## Data Schema: `InventoryItem` (Internal Standard)
This schema maps directly to the eBay Inventory API requirements.

```json
{
  "sku": "String (Unique Identifier, e.g., '2026-ITEM-001')",
  "product": {
    "title": "String (MAX 80 chars)",
    "description": "String (HTML allowed, must be mobile-friendly)",
    "aspects": {
      "Brand": ["String"],
      "Type": ["String"],
      "Color": ["String"],
      "...": ["..."]
    },
    "imageUrls": ["String (URL)"],
    "brand": "String",
    "mpn": "String (Optional)",
    "upc": ["String (Optional)"]
  },
  "condition": "String (Enum: NEW, LIKE_NEW, USED_EXCELLENT, USED_GOOD, USED_FAIR, FOR_PARTS)",
  "conditionDescription": "String (Text description of flaws)",
  "availability": {
    "shipToLocationAvailability": {
      "quantity": 1
    }
  }
}
```

## Data Schema: `Offer` (Internal Standard)
The specifics for how the item is sold.

```json
{
  "sku": "String (Match InventoryItem SKU)",
  "marketplaceId": "EBAY_US",
  "format": "FIXED_PRICE",
  "listingDescription": "String (HTML content - usually same as product.description)",
  "pricingSummary": {
    "price": {
      "value": "String (Format: '19.99')",
      "currency": "USD"
    }
  },
  "listingPolicies": {
    "fulfillmentPolicyId": "String (ID from Account)",
    "paymentPolicyId": "String (ID from Account)",
    "returnPolicyId": "String (ID from Account)"
  },
  "categoryId": "String (Leaf Category ID)",
  "merchantLocationKey": "String (Zip/Location Key)"
}
```

## Core SOPs (Architecture)
Refer to the `architecture/` directory. Updates here drive code changes.

## Governance
- **Self-Healing Loop**: Document errors in `findings.md` before fixing.
- **Progress Tracking**: Log major milestones in `progress.md`.
