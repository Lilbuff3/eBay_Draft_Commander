# Hermes → Draft Commander capture

Bridge that turns WhatsApp photos into eBay **scheduled** listings, using Draft Commander
(DC) as the unchanged engine. Hermes = capture + notify; DC = analyze + schedule. See the
design/plan under `docs/superpowers/`.

## Mode: WhatsApp self-chat + keyword
This Hermes runs in WhatsApp **self-chat mode** — it watches your "Message yourself" chat,
not a separate number. To avoid every photo becoming a listing, capture is gated by a
**caption keyword**: only photos you caption with **"sell"** are listed. (No
`EBAY_CAPTURE_CHAT_ID` is needed in this mode — the keyword is the gate.)

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
   - `DC_REPO=C:/Users/adam/Projects/ebay-draft-commander`
   - `DC_API_BASE=http://127.0.0.1:5000`
   - `DC_CAPTURES_DIR=C:/Users/adam/Projects/ebay-draft-commander/captures`
     (must match DC's `CAPTURES_DIR` = `<repo>/captures`, a sibling of `inbox/`.)
3. Make sure the python Hermes invokes can import `pillow` and `requests`
   (use DC's venv, or `uv pip install pillow requests`).
4. Restart Hermes so it loads the new skill.

## Use
- In WhatsApp on the linked number, open **"Message yourself"** and send an item's photos
  in one message with a caption containing **"sell"** → you get a status line back with a
  `job <id>`. The listing is scheduled into the next eBay peak window; review/edit it in
  Seller Hub before it goes live.
- Reply **"cancel last"** → ends the eBay listing (if created) and removes the DC job.

## Requires
- Draft Commander running: `python backend/wsgi.py` (port 5000).
- eBay business policies + token configured in DC's `.env` (the listing won't schedule otherwise).

## Tests
`python -m pytest tests/unit/test_capture_bridge.py -v` (run from the repo root).
