# SOP: Navigation Layer (Inbox processing)

## Purpose
To automate the flow from "Files in Folder" to "Draft on eBay".

## The Navigation Pipeline

### 1. The Watcher (`tools/process_inbox.py`)
- **Role**: The Eyes.
- **Action**: Scans `inbox/` for subdirectories.
- **Logic**:
    - Ignores empty folders.
    - Ignores folders already in `QueueManager` (checked via DB).
    - Adds new folders to `QueueManager`.

### 2. The Queue (`QueueManager`)
- **Role**: The Conductor.
- **Action**: Persists jobs in SQLite. Handles Retries.
- **Logic**: Dispatches jobs to `ProcessorService`.

### 3. The Processor (`ProcessorService`)
- **Role**: The Worker (Refactored).
- **Workflow**:
    1.  **AI Analysis**: Generates Title, Description, Aspects.
    2.  **Pricing**: Calculates Price.
    3.  **Templating**: Merges data into `ebay_master.html`.
    4.  **Inventory Service**:
        - `create_inventory_item()` (Catalog Data).
        - `create_offer()` (Listing Data + Policies).
    5.  **Move**: Moves folder from `inbox/` to `ready/` (or `posted/`).

## Key Dependencies
- `InventoryService` (Phase 2 Link).
- `TemplateManager` (Phase 4 Stylize).
