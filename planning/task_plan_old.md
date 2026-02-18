# Task Plan - B.L.A.S.T. Protocol

## Phase 0: Initialization
- [x] Initialize Project Memory (`gemini.md`, `findings.md`, `progress.md`)
- [x] Create `task_plan.md` (This file)
- [x] Discovery Questions Answered

## Phase 1: B - Blueprint (Vision & Logic)
- [x] Define North Star (Confirmed)
- [x] Confirm Integrations & Keys
- [x] Define Data Schema
- [x] Research phase

## Phase 2: L - Link (Connectivity)
- [x] Verification: Test all API connections
- [x] Handshake: Build minimal scripts in `tools/`

## Phase 3: The Engine Room (Backend & Services)
Focus on stability, data integrity, and core logic.
- [x] **3.1 Service Migration**: Move logic from `tools/` to `backend/services/` (Queue, eBay, Pricing).
- [x] **3.2 Data Layer**: Solidify the SQLite database (`commander.db`) as the single source of truth.
- [x] **3.3 API Layer**: Ensure the Flask API (`/api/`) fully exposes all service capabilities to the frontend.

## Phase 4: The Control Center (Frontend Core)
Focus on functionality and "making it work" visually.
- [x] **4.1 Wiring**: Connect the Electron frontend to the Flask API (fetch jobs, show status).
- [x] **4.2 Real-time Sync**: Implement Socket.IO for live progress bars and console logs.
- [x] **4.3 Basic Controls**: "Start", "Stop", "Pause", and "Retry" buttons working physically.

## Phase 5: The Smart Assistant (Intelligence & Automation)
Focus on the unique value props (AI, Automation).
- [ ] **5.1 AI Pipeline**: Refine the prompt engineering for Title/Description generation.
- [ ] **5.2 Hands-free Mode**: Finalize the "Auto-Publish" workflows and safety checks.
- [ ] **5.3 Bulk Operations**: Drag-and-drop folder processing.

## Phase 6: Polish & Release (UI/UX)
Focus on "wow" factor and distribution.
- [ ] **6.1 Visuals**: Apply the "Premium/Glassmorphism" styling.
- [ ] **6.2 Packaging**: Build the `.exe` for easy distribution.
- [ ] **6.3 User Manual**: Finalize documentation.
