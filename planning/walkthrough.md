# Inventory & Analytics Debugging Walkthrough

This document summarizes the fixes implemented to resolve the zero price issue in inventory and the disappearing analytics dashboard.

## 1. Zero Price Inventory Fix

**Issue**: Inventory items were displaying $0.00 because the eBay Inventory API (`/inventory_item`) does not return price information. Fetching prices individually for each SKU was causing timeouts.

**Fix**: Switched the `/api/listings/active` endpoint in `web_server.py` to use the **eBay Trading API (`GetMyeBaySelling`)**. This API returns all active listings with their current price in a single call, efficiently solving the issue.

### Changes in `web_server.py`

```python
# Before: Inventory API (No Price)
# response = requests.get(f'{INVENTORY_URL}/inventory_item', ...)

# After: Trading API (Includes Price)
xml_request = f"""
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  ...
  <ActiveList>
    <Sort>TimeLeft</Sort>
    ...
  </ActiveList>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBaySellingRequest>
"""
# ... XML parsing to extract CurrentPrice ...
```

## 2. Analytics Disappearing Fix

**Issue**: The analytics data would load briefly and then disappear. This was caused by a React anti-pattern in `Dashboard.tsx` where the `DashboardContent` component was defined *inside* the `Dashboard` component's render function. This caused the component (and its child `SalesWidget`) to be destroyed and recreated on every state update.

**Fix**: Refactored `Dashboard.tsx` to move `DashboardContent` outside of the main component. Passed necessary state via props. This ensures the component tree remains stable and state (like fetched analytics data) is preserved.

### Changes in `Dashboard.tsx`

```typescript
// Before: Defined inside component
export function Dashboard() {
  // ... state ...
  const DashboardContent = ({ isMobile }) => ( ... ) // Re-created on every render!
  return <DashboardContent ... />
}

// After: Defined outside
const DashboardContent = ({ ...props }: DashboardContentProps) => ( ... )

export function Dashboard() {
  // ... state ...
  return <DashboardContent ...props /> // Stable component reference
}
```

## Verification

- **Backend**: `web_server.py` passed syntax check (`python -m py_compile`).
- **Frontend**: Project built successfully (`npm run build`).

The application should now correctly display inventory prices and maintain stable analytics data.

# Architecture Migration: "Kill Tkinter" Strategy

We have successfully laid the foundation to deprecate the Python Tkinter GUI in favor of a modern Electron + React architecture.

## Summary of Changes

1.  **Backend Parity**:
    *   Updated `web_server.py` to use the same `create_listing_structured` processor as the desktop app, ensuring identical behavior.
    *   Added `/api/settings` endpoints to manage `.env` configuration from the web UI.

2.  **Frontend Enhancements**:
    *   **Settings Page**: Created a new tabbed interface (`/settings`) for managing API Keys and Policies.
    *   **Routing**: Updated `App.tsx` and `Dashboard.tsx` to integrate the Settings page.

3.  **Electron Integration**:
    *   **Wrapper**: Created `frontend/electron/main.js` to manage the lifecycle of both the React frontend and the Python backend.
    *   **Scripts**: Added `npm run electron:dev` for development and `electron-builder` configuration for production.
    *   **Spec**: Created `server.spec` for PyInstaller to bundle the backend.

## How to Test

### Development Mode
To run the full desktop experience with hot-reloading:

```bash
cd frontend
npm run electron:dev
```

This will:
1.  Start the Vite dev server (React).
2.  Start the `web_server.py` backend (Python) as a child process.
3.  Launch the Electron window.

![Vite Dev Server Confirmation](file:///C:/Users/adam/.gemini/antigravity/brain/8d9498ff-7b1b-4f30-a37c-392aa6a56562/vite_dev_server_dashboard_1768996015786.png)

**Note**: Ensure existing Python instances are closed before running.


### Next Steps (Production Build)
To create the distributable `.exe`:
1.  Compile Python: `pyinstaller server.spec`
2.  Build Electron: `npm run electron:build`

