# Architecture Migration: Electron Wrapper

- [ ] Backend Preparation
    - [ ] Unify `web_server.py` processor logic (Use `create_listing_structured`)
    - [ ] Implement Settings API (`GET`, `POST` /api/settings)
- [ ] Frontend Implementation
    - [ ] Create Settings Page (`Settings.tsx`)
    - [ ] Add Settings Route and Sidebar Link
    - [ ] Integrate Settings API
- [ ] Electron Integration
    - [ ] Install Electron dependencies
    - [ ] Create Main Process (`main.js`) & Preload
    - [ ] Configure `electron-builder`
- [ ] Packaging & Verification
    - [ ] Build Standalone Python Server
    - [ ] Build Electron App
    - [ ] Verify Drag & Drop and Settings
