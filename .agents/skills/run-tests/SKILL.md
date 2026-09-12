---
name: run-tests
description: Run backend Python 3.12 unit tests and frontend vitest suite. Use to verify code changes before completion.
---

# Run Test Suites

## Steps
1. Backend unit tests — **must use the Python 3.12 install** (bare `python`/`py` may resolve to a Python 3.13 without project dependencies):
   ```powershell
   cd C:\Users\adam\Projects\ebay-draft-commander
   & "C:\Program Files\Python312\python.exe" -m pytest tests/unit -q
   ```

2. Frontend tests:
   ```powershell
   cd C:\Users\adam\Projects\ebay-draft-commander\frontend
   npx vitest run
   ```

### Expectations
- Expected baseline: ~829 backend unit tests, ~50 frontend tests, all green.
- **Caution:** Integration tests (`tests/integration/`) need live eBay sandbox credentials — do not run them casually.
