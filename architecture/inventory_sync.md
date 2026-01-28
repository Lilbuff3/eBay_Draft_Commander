# SOP: Inventory Sync (`inventory_sync.py`)

## Purpose
Keeps the local application state in sync with the live eBay marketplace. It fetches active listings and updates metadata like quantity, price, and titles.

## Location
`tools/inventory_sync.py`

## Core Features

### 1. Active Listing Retrieval
- Uses the **eBay Inventory API** to fetch all inventory items.
- Aggregates pagination results into a local list.

### 2. Bulk Updates
- Supports batch updating prices across multiple SKUs.
- Synchronizes quantity between local database (data/inventory) and eBay.

### 3. SKU Management
- Maps local folder names or IDs to eBay SKUs (prefix: `DC-`).

## Usage Example
```python
from tools.inventory_sync import get_inventory_sync

syncer = get_inventory_sync()
active_items = syncer.get_all_active_listings()
```
