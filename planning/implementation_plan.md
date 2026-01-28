# Repository Cleanup Implementation Plan

## Goal Description
Clean up the `ebay-draft-commander` repository by removing unnecessary, redundant, and outdated files identified in the recent audit. This will improve maintainability and reduce clutter.

## User Review Required
> [!WARNING]
> **Deletion Risk**: This plan involves moving files to an `archive/_deprecated_2026_01_25` directory and deleting temporary files. 
> Please review the "Proposed Changes" section carefully to ensure no critical files are marked for removal.
> **Specific Note**: The legacy desktop UI Python files (`inventory_dialog.py`, etc.) will be archived. If you still use the desktop GUI (TKinter/Qt), let me know immediately.

## Proposed Changes

### 1. Archiving Dead Code
Create a new directory `archive/_deprecated_2026_01_25` and move the following files there:

#### Legacy Modules
- `legacy_draft_commander.py`
- `legacy_web_server.py`
- `auto_refresh.py`
- `create_shortcut.py`
- `smart_listing.py`

#### Obsolete Desktop UI Components
- `inventory_dialog.py`
- `photo_editor_dialog.py`
- `preview_dialog.py`
- `settings_dialog.py`
- `template_dialog.py`
- `ui_widgets.py`

#### Unused Frontend Components
- `frontend/src/components/TestMediaManager.tsx`

### 2. Archiving Unused Assets
Move the following to `archive/_unused_assets`:

- `phone_screenshot*.png`
- `phone_test*.png`
- `mobile_access_qr.png`
- `mobile_access_vite_qr.png`

### 3. Cleaning Temporary Files
**DELETE** the following files:

- `ai_test_output.txt`, `ai_trust_output.txt`, `api_debug.txt`
- `cletop_output.txt`, `post_cletop_log.txt`
- `debug_output.txt`, `debug_output_2.txt`
- `e2e_log.txt`, `health_report.txt`
- `offer_debug.txt`, `pricing_test.txt`
- `user_test_output.txt`
- `debug_ebay_output.html`
- `frontend/build_error.log`

### 4. Updates to .gitignore
#### [MODIFY] [.gitignore](file:///c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/.gitignore)
- Add patterns to ignore future occurrences of these temporary files.
    ```
    *_output.txt
    *_log.txt
    debug_*.html
    pricing_test.txt
    ```

## Verification Plan

### Manual Verification
1.  **Build Check**: Run `npm run build` in `frontend/` to ensure no archived assets were critical.
2.  **Backend Check**: Run `python tools/verify_system_health.py` to ensure core backend services still function.
3.  **Visual Check**: Verify the `archive/` folder contains the expected items.
