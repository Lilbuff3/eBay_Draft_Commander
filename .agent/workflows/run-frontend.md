---
description: Start the Vite dev server for frontend development
---

## Start Frontend Dev Server

// turbo
1. Navigate to frontend and start dev server:
```
cd c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\frontend && npm run dev
```

The dev server will start at http://localhost:5173 with hot module replacement.

API calls to `/api/*` are proxied to Flask on port 5000, so make sure the Flask server is running:
```
python web_server.py
```
