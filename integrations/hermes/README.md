# Hermes → Draft Commander capture

Bridge that turns photos sent to a dedicated Hermes WhatsApp chat into eBay **scheduled**
listings, using Draft Commander (DC) as the unchanged engine. Hermes = capture + notify;
DC = analyze + schedule. See the design/plan under `docs/superpowers/`.

## Components
- `capture_to_dc.py` — the bridge script (version-controlled + unit-tested here). Normalizes an
  item's photos to ordered JPEGs, writes them under DC's captures dir, calls `POST /api/capture`,
  polls the job, and prints a WhatsApp-ready status line.
- `SKILL.md` — source-of-truth copy of the Hermes skill. Install it into Hermes (below).

## Install (one-time)
1. Copy the skill into Hermes' user-local skills tree:
   `C:\Users\adam\AppData\Local\hermes\skills\productivity\ebay-capture\SKILL.md`
   (copy of `integrations/hermes/SKILL.md`).
2. Add to `C:\Users\adam\AppData\Local\hermes\.env`:
   - `DC_REPO=C:\Users\adam\Projects\ebay-draft-commander`
   - `DC_API_BASE=http://127.0.0.1:5000`
   - `DC_CAPTURES_DIR=C:\Users\adam\Projects\ebay-draft-commander\captures`
     (must match DC's `CAPTURES_DIR`, which is `<repo>/captures` — a sibling of `inbox/`.
     If you set `INBOX_PATH` in DC's `.env`, captures becomes `<INBOX_PATH>/../captures`; keep these in sync.)
   - `EBAY_CAPTURE_CHAT_ID=<the WhatsApp chat/group id to dedicate as the eBay inbox>`
3. Make sure the python Hermes invokes can import `pillow` and `requests`
   (use DC's venv, or `uv pip install pillow requests`).
4. Find the chat id in Hermes' `channel_directory.json` after sending one message from the
   chat you want to dedicate.

## Use
- Send an item's photos (one WhatsApp message) to the dedicated eBay chat → you get a status line
  back with a `job <id>`. The listing is scheduled into the next eBay peak window; review/edit it in
  Seller Hub before it goes live.
- Reply "cancel last" → ends the eBay listing (if created) and removes the DC job.

## Requires
- Draft Commander running: `python backend/wsgi.py` (port 5000).
- eBay business policies + token configured in DC's `.env` (the listing won't schedule otherwise).

## Tests
`python -m pytest tests/unit/test_capture_bridge.py -v` (run from the repo root).
