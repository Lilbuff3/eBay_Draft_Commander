---
description: Build frontend for production
---

## Build Frontend for Production

// turbo
1. Build the Vite app (tsc + vite, outputs to ../static/app):
```
cd C:\Users\adam\Projects\ebay-draft-commander\frontend && npm run build
```

After building, Flask serves the app at http://localhost:5000/app

**Always run this before committing frontend changes, and commit the regenerated `static/app/` output together with the source change** — production serves the committed build, not a live compile.
