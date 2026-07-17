---
description: Run backend unit tests and frontend vitest
---

## Run Tests

// turbo
1. Backend unit tests — **must use the Python 3.12 install**; bare `python`/`py` may resolve to a 3.13 without project deps:
```
cd C:\Users\adam\Projects\ebay-draft-commander && "C:\Program Files\Python312\python.exe" -m pytest tests/unit -q
```

// turbo
2. Frontend tests:
```
cd C:\Users\adam\Projects\ebay-draft-commander\frontend && npx vitest run
```

Expected (2026-07): ~829 backend unit tests, ~50 frontend tests, all green. Integration tests (`tests/integration/`) need live eBay credentials — don't run them casually.
