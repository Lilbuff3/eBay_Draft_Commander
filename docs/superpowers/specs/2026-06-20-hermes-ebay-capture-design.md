# Hermes → eBay Scheduled-Listing Capture — Design

- **Date:** 2026-06-20
- **Status:** Approved (pending spec review)
- **Author:** Adam + Claude
- **Topic:** Bridge NousResearch Hermes (personal agent) into eBay Draft Commander as a photo-capture front end that produces eBay *scheduled* listings.

## Goal

Snap photos of an item on your phone, send them to Hermes over WhatsApp, and have a fully analyzed eBay **scheduled listing** appear in Seller Hub — no folders, no app, no manual steps. Draft Commander (DC) remains the analysis/listing engine; Hermes is only the capture + notification layer.

## Non-Goals

- **No rebuild of DC's pipeline.** Vision, category mapping, pricing cascade, item-specifics, no-blocks aspect resolver, and Trading-API listing creation are reused unchanged.
- **No conversational queue control** (approve/edit/price by chat) in v1. Possible future phase.
- **No swap of the AI model.** Gemini pipeline stays.
- **No new eBay "draft" path.** Destination is a scheduled live listing, editable in Seller Hub before go-live.

## Locked Decisions

| Decision | Choice |
|---|---|
| Architecture | Hermes = capture + notify. DC = engine + scheduler. Integrate, do not reimplement. |
| Capture channel | WhatsApp (already paired in Hermes). |
| Photo grouping | One WhatsApp message = one item (all of an item's photos in a single message). |
| Capture trigger | **Dedicated WhatsApp "eBay" chat** — any photo posted in that chat is an item. Photos in other chats are untouched (Hermes' other skills keep working). |
| Destination | eBay **scheduled** listing (Trading API `ScheduleTime`), editable in Seller Hub before go-live. |
| Schedule timing | **Next evening, staggered** — DC assigns slots in an evening window, spaced apart. |
| Confidence gate | **None** — pure fire-and-forget; every item auto-schedules regardless of confidence. |
| Safety net | "Cancel last" command + the schedule delay (review window in Seller Hub). |
| Integration mechanism | Staging dir + dedicated `POST /api/capture` endpoint (NOT generic scan — see Race section). |

## Key Constraint Discovered (drives the design)

`queue_manager.py:445` `_watch_inbox` runs a **background watcher every 10 seconds** that scans `inbox/`, creates a job on the first image it sees, and auto-starts processing. This forces two design choices:

1. **Atomic folder publication.** Hermes must assemble an item's photos in a **staging directory outside `inbox/`**, then **atomically move/rename the complete folder into `inbox/`** (single rename). Otherwise the 10s watcher can grab a half-written folder and create a job with missing images.
2. **Dedicated capture endpoint.** The generic watcher cannot carry "auto-schedule" intent or assign a schedule slot *before* processing begins. A dedicated `POST /api/capture` endpoint performs move-in + job creation + slot assignment atomically, then lets processing run. The watcher remains for the legacy PWA/manual flow.

## Architecture

```
 Phone (WhatsApp)
      │  dedicated eBay chat · one message = one item's photos
      ▼
 Hermes Agent  ──────────────── eBay-capture SKILL ─────────────────┐
   • receives images (image_cache)                                   │
   • normalize → .jpg, order-preserved (01,02,…) = cover first       │
   • write to STAGING dir (outside inbox)                            │
   • POST /api/capture { staging_path }                              │
   • poll GET /api/jobs/<id> until terminal                          │
   • WhatsApp notify (scheduled / failed)                            │
   • "cancel last" → POST /api/jobs/<id>/cancel                      │
                                                                     │
 Draft Commander (Flask, localhost:5000)  ◀─────────────────────────┘
   • POST /api/capture: atomic move staging→inbox/<uuid>/,
       create job (metadata: capture_source=hermes, auto_schedule=true),
       assign staggered evening slot (atomic), return job_id + scheduled_time
   • existing pipeline: vision → category → pricing → specifics → no-blocks resolver
   • existing scheduled_time → Trading API <ScheduleTime>
   • POST /api/jobs/<id>/cancel: EndFixedPriceItem (if listed) + remove job
      │
      ▼
 eBay Seller Hub → Scheduled  (editable until go-live)
```

## Flow (happy path)

1. You snap an item's photos and send them in **one WhatsApp message to the dedicated eBay chat**.
2. The Hermes eBay-capture skill collects that message's images, normalizes each to `.jpg`, and names them by send order (`01.jpg`, `02.jpg`, …) so the **first photo becomes the eBay cover**.
3. Skill writes the images into a **staging folder** (e.g. `<DC>/staging/<uuid>/`), outside `inbox/`.
4. Skill calls `POST /api/capture` with the staging folder path.
5. DC validates the path, **atomically moves** the folder to `inbox/<uuid>/`, creates a job with metadata `{capture_source: "hermes", auto_schedule: true}`, **assigns the next staggered evening slot** (atomic, see Scheduling), stores it as `scheduled_time`, and returns `{ job_id, scheduled_time }`.
6. DC's normal pipeline processes the job (vision → category → pricing → specifics → no-blocks resolver), then creates the Trading-API listing with `<ScheduleTime>` = `scheduled_time`. Listing lands in **Seller Hub → Scheduled**.
7. Hermes **polls** `GET /api/jobs/<job_id>` until terminal, then sends WhatsApp:
   - success → `✅ Scheduled: <title> — $<price> — live <local time>`
   - failure → `❌ Couldn't analyze <uuid> (bad photos?) — nothing scheduled.`
8. If you reply **"cancel last"**, Hermes calls `POST /api/jobs/<job_id>/cancel`; DC ends the eBay scheduled listing (`EndFixedPriceItem`) if already created, otherwise just removes the job, and confirms.

## Components: Reused vs New

| Reused (no change) | New (to build) |
|---|---|
| `_watch_inbox` (legacy manual flow) | `POST /api/capture` endpoint (DC) |
| `scanner_service` folder=item model | Staggered-slot assigner (DC) |
| Full AI pipeline / processor_service | `POST /api/jobs/<id>/cancel` endpoint (DC) — or extend existing remove_job + EndFixedPriceItem |
| `scheduled_time` → `trading.py` `<ScheduleTime>` | Hermes eBay-capture skill (`SKILL.md` + bridge script) |
| No-blocks aspect resolver | `capture_source` / `auto_schedule` job metadata |
| `jobs_api` `GET`/`PATCH`, validators | — |

## DC: `POST /api/capture` contract

Request (JSON):
```json
{ "staging_path": "<absolute path to a complete folder of images>" }
```
Behavior:
- Validate `staging_path` via existing `validate_safe_path`.
- Reject if it contains no images (existing `SUPPORTED_IMAGE_EXTENSIONS`).
- `os.rename` (atomic, same filesystem) the folder to `inbox/<uuid>/`.
- `queue_manager.add_folder(...)` with metadata `{capture_source:"hermes", auto_schedule:true}`.
- Assign staggered slot (below); persist as `scheduled_time` **before** the job reaches the create-listing step (`processor_service.py:585` reads it).

Response (JSON):
```json
{ "job_id": "<8hex>", "scheduled_time": "<ISO 8601 UTC>", "status": "scheduled_pending_analysis" }
```

## Scheduling: staggered evening slots

- **Window:** 18:00–21:00 in the seller's local timezone (configurable). Default tz `America/Los_Angeles` (user's local).
- **Spacing:** 25 minutes → slots at 18:00, 18:25, …, 20:50 (7 slots/evening).
- **Assignment:** choose the earliest slot that is (a) ≥ `now + 1h` (eBay minimum lead), (b) not already taken by another scheduled job. Query existing `jobs.scheduled_time` (indexed: `idx_jobs_scheduled_time`).
- **Atomicity:** assignment runs inside a DB transaction / lock so two near-simultaneous captures cannot claim the same slot. SQLite WAL + `busy_timeout=5000` already configured.
- **Overflow:** when tonight's window is full, roll to the next evening, up to eBay's **21-day** cap (`constants.py:171`). If all evenings within 21 days are full, **do not exceed the cap** — leave the job unscheduled (status indicates "needs scheduling") and notify the user.

## Hermes: eBay-capture skill

- Authored per `software-development/hermes-agent-skill-authoring/SKILL.md` (read during planning).
- Skill folder with `SKILL.md` instructing Hermes: **on a photo message in the dedicated eBay chat** (identified by channel/contact id), run the bridge script. Photos in any other chat are ignored by this skill.
- Bridge script (Python, runs under Hermes' bundled `uv`):
  - Read inbound image paths (confirm Hermes' inbound-media location, likely `image_cache/` — verify in planning).
  - Normalize each to `.jpg` (handle webp/HEIC); name `01.jpg`, `02.jpg`, … in send order.
  - Write to `<DC>/staging/<uuid>/`.
  - Health-check DC (`GET /api/system/health`); if down, retain photos in staging and notify "DC offline — will retry".
  - `POST /api/capture`; on success, poll `GET /api/jobs/<id>` (exponential backoff, cap ~5 min) until terminal; send WhatsApp result.
  - Track last `job_id`(s) to support "cancel last".

## Error Handling

- **DC offline:** skill detects via health check; keeps staged photos, notifies, retries (Hermes cron or next message). No photos dropped.
- **Pipeline failure (job → failed):** notify failure; nothing scheduled.
- **Low confidence:** per decision, still auto-schedules. Notification *may* append `⚠ low confidence` as an FYI (no gate). Optional.
- **>12 images:** eBay caps at 12; DC already trims silently. Skill should warn if a message exceeds 12 so the user knows extras are dropped.
- **Non-item photos:** only photos posted in the dedicated eBay chat are listed, so an accidental listing requires posting a non-item there. Still mitigated by schedule delay + "cancel last".
- **21-day overflow:** job left unscheduled + notified (see Scheduling).

## Cancel / Undo

- Command "cancel last" (and synonyms) → `POST /api/jobs/<job_id>/cancel`.
- DC: if a scheduled eBay listing was already created, call `EndFixedPriceItem` (exists in `trading.py`) then remove the job; if not yet listed, just remove the job (reuse `remove_job`).
- Verify/confirm a cancel route exists or add a thin one; confirm `EndFixedPriceItem` is wired for scheduled (not-yet-live) items.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Watcher grabs partial folder | Atomic staging→inbox rename; watcher only sees complete folders |
| Slot collision on rapid captures | Atomic DB slot assignment |
| Accidental listing from a stray photo | Dedicated eBay chat scopes capture — other chats untouched; schedule delay + "cancel last" as nets |
| Bad AI listing goes live (no confidence gate) | Scheduled (not instant); review/edit/delete in Seller Hub before go-live; "cancel last" |
| Slot assigned after create-listing step | Assign at capture time, before processing reaches `processor_service:585` |
| eBay rejects incomplete scheduled listing | No-blocks aspect resolver already auto-fills required aspects |

## Open Items to Verify During Planning

1. Hermes inbound-media location (confirm `image_cache/` path + how the skill receives image file paths).
2. Existing DC auto-schedule logic — observations S529 ("scheduling/automation distributed across services") and 543 ("auto-scheduling decoupled from auto_publish"). Reuse if it already assigns slots; avoid duplicating.
3. Cancel route + `EndFixedPriceItem` behavior for scheduled-but-not-live listings.
4. Seller timezone source (env/setting) for the evening window.
5. Whether `add_folder` should accept metadata directly vs PATCH immediately after creation.
6. How Hermes identifies the dedicated eBay chat (channel/contact id, likely from `channel_directory.json`) so the skill triggers only there.

## Testing

- **DC unit:** slot assigner (spacing, ≥1h lead, overflow, 21-day cap, atomicity); `/api/capture` (atomic move, metadata, response); cancel (listed vs not-listed).
- **DC integration:** full capture → scheduled listing in eBay sandbox using `tests/fixtures/images/` (e.g. `boombox/`), then cancel/cleanup.
- **Hermes skill:** local script test — drop sample images, assert staging layout, `/api/capture` call, notification text, "cancel last".
- **Manual E2E:** real WhatsApp photo → Seller Hub Scheduled entry → edit → let go live (or cancel).

## Build Order (for the implementation plan)

1. DC: staggered-slot assigner (+ unit tests).
2. DC: `POST /api/capture` (staging→inbox atomic move, job + metadata + slot) (+ tests).
3. DC: `POST /api/jobs/<id>/cancel` (+ tests).
4. Hermes: bridge script (normalize, stage, capture call, poll, notify).
5. Hermes: `SKILL.md` (+ register skill).
6. E2E in eBay sandbox; then live smoke with one real item.
