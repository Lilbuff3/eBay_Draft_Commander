---
name: run-frontend
description: Start the Vite dev server for frontend development. Use when working on React UI components or frontend code.
---

# Start Frontend Dev Server

## Steps
1. Navigate to the frontend directory and start the Vite dev server:
   ```powershell
   cd C:\Users\adam\Projects\ebay-draft-commander\frontend
   npm run dev
   ```

2. The dev server starts at `http://localhost:5175` with hot module replacement (HMR).

3. **Backend dependency:** API calls to `/api/*` are proxied to Flask on port 5000. Make sure the backend is running (see `/run-backend`). If it isn't running:
   ```powershell
   cd C:\Users\adam\Projects\ebay-draft-commander
   python backend/wsgi.py
   ```
