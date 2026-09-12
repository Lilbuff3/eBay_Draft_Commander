---
name: build-frontend
description: Build the Vite React frontend for production and output to static/app. Use before committing frontend changes.
---

# Build Frontend for Production

## Steps
1. Build the Vite app (`tsc` + `vite`, outputs to `../static/app`):
   ```powershell
   cd C:\Users\adam\Projects\ebay-draft-commander\frontend
   npm run build
   ```

2. After building, Flask serves the app at `http://localhost:5000/app`.

3. **Critical Rule:** Always run this before committing frontend changes, and commit the regenerated `static/app/` output together with the source changes. Production serves the committed build, not a live compile.
