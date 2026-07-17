---
description: Start the Vite dev server for frontend development
---

## Start Frontend Dev Server

// turbo
1. Navigate to frontend and start dev server:
```
cd C:\Users\adam\Projects\ebay-draft-commander\frontend && npm run dev
```

The dev server starts at http://localhost:5175 with hot module replacement.

API calls to `/api/*` are proxied to Flask on port 5000, so make sure the backend is running (see /run-backend). If it isn't:
```
cd C:\Users\adam\Projects\ebay-draft-commander && python backend/wsgi.py
```
