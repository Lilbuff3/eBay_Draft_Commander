# Findings & Self-Healing Log

This file documents every error, inconsistency, or bug encountered during development.
The rule: Document here **before** fixing code.

## Log

### [2026-01-24] - Initial Audit
- **Status**: Clean slate. No active errors detected yet.
- **Context**: Performing Phase B Data Capture and Phase A Architecture Backfill.
- **Finding**: Root directory is cluttered with 90+ files, mostly standalone scripts. Needs immediate migration to `tools/`. (Resolved)

### [2026-01-24] - Health Check Failure
- **Error**: `[FAIL] Settings crashed: No module named 'backend'` in `verify_system_health.py`.
- **Cause**: Script was moved to `tools/` folder, but its internal `sys.path` logic still pointed to its current directory (now `tools/`) instead of the project root.
- **Impact**: Verification script fails to load application settings.

### [2026-01-24] - Inventory API Header Error
- **Error**: `invalid header name or value for header Content-Language`.
- **Cause**: `InventoryService` requires `Content-Language: en-US` header for PUT/POST operations. Missing in `policies._get_headers()`.
- **Fix**: Updated `_get_headers` to include `Content-Language`.
