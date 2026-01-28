# SOP: eBay API Client (`ebay_api.py`)

## Purpose
The `eBayAPIClient` is the primary interface for interacting with eBay's RESTful APIs. It handles authentication (OAuth 2.0) and provides high-level methods for common tasks like category suggestions and aspect retrieval.

## Location
`tools/ebay_api.py`

## Key Functions

### 1. Authentication (`get_access_token`)
- **Mechanism**: OAuth 2.0 Client Credentials Grant.
- **Scope**: `https://api.ebay.com/oauth/api_scope`
- **Behavior**: Retrieves a short-lived access token using `EBAY_APP_ID` and `EBAY_CERT_ID`. Caches the token for the lifetime of the client instance.

### 2. Category Suggestions (`get_category_suggestions`)
- **API**: Commerce Taxonomy API (`/get_category_suggestions`)
- **Input**: Query string (e.g., "vintage camera").
- **Output**: List of suggested categories with `category_id` and `full_path`.

### 3. Item Aspects (`get_item_aspects`)
- **API**: Commerce Taxonomy API (`/get_item_aspects_for_category`)
- **Input**: `category_id`.
- **Output**: Dictionary separating `required` and `optional` item specifics (e.g., Brand, Size, Color).

## Usage Example
```python
from tools.ebay_api import eBayAPIClient

client = eBayAPIClient()
suggestions = client.get_category_suggestions("fiber optic cleaner")
if suggestions:
    category_id = suggestions[0]['category_id']
    aspects = client.get_item_aspects(category_id)
```

## Dependencies
- `requests`: For HTTP calls.
- `.env`: Must contain `EBAY_APP_ID` and `EBAY_CERT_ID`.

## Maintenance
Update the `TAXONOMY_URL` or `AUTH_URL` if eBay deprecates existing versions. Default `CATEGORY_TREE_ID` is `0` (US Marketplace).
