# Debugging Inventory & Analytics Plan

## Goal Description
Resolve two critical issues reported by the user:
1.  **Zero Price in Inventory**: Inventory items are displaying a price of $0.00. This is likely due to the API optimization in `web_server.py` that skips fetching offer details (price) for each item to save time.
2.  **Analytics Disappearing**: The analytics dashboard loads data briefly but then it vanishes. This suggests a frontend state issue, potentially a re-render clearing data or an error causing the component to unmount/hide.

## User Review Required
None at this stage.

## Proposed Changes

### Inventory Price Fix
The `get_active_listings` endpoint in `web_server.py` needs to provide price information.
-   **Analyze**: Check if price is available in the initial `get_inventory_items` response (it might be in a different field) or if we need a batch fetch for offers.
-   **Modify**: `web_server.py` to include price in the returned JSON.
-   **Modify**: `ActiveListings.tsx` to ensure it reads the correct price field.

### Analytics Fix
-   **Analyze**: `Dashboard.tsx` and `SalesWidget.tsx` (if it exists) or the relevant analytics section in `Dashboard.tsx`.
-   **Debug**: Use browser console to check for errors.
-   **Modify**: Fix the state management or error handling causing the data to disappear.

## Verification Plan

### Automated Tests
-   None.

### Manual Verification
-   **Inventory**: Reload "Inventory Sync" and verify valid prices are displayed for items.
-   **Analytics**: Reload the dashboard and verify the analytics widgets stay visible and populated.
