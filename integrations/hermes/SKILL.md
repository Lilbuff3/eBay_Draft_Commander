---
name: ebay-capture
description: Use when a photo captioned "sell" arrives in the WhatsApp self-chat. Turns that message's photos into one eBay scheduled listing via Draft Commander; supports "cancel last".
version: 1.0.0
author: Adam
license: MIT
metadata:
  hermes:
    tags: [ebay, selling, capture, draft-commander]
    related_skills: [productivity]
---

# eBay Capture

## Overview
Turn WhatsApp photos into eBay **scheduled** listings via Draft Commander (DC). This Hermes
runs in WhatsApp **self-chat mode**, so it watches your note-to-self chat. To avoid every
photo becoming a listing, the trigger is a **caption keyword**: only photos you caption with
**"sell"** are listed. One message = one item. DC schedules the listing into an eBay peak
window; review/edit it in Seller Hub before it goes live.

## When to Use
- A self-chat message has **one or more photos AND a caption/text containing the word
  "sell"** (case-insensitive). That message = one item.
- The user says **"cancel last"** / "undo last".
- **Don't use for:** photos WITHOUT a "sell" caption (ignore them / leave for other skills),
  or any text that isn't a cancel request.

## Capture a new item
1. Confirm the message has at least one image AND its caption/text contains "sell". If not, do nothing here.
2. Collect ALL image attachments of THIS message, in order, and resolve their on-disk paths.
3. Run the bridge via the `terminal` tool (DC_API_BASE / DC_CAPTURES_DIR are read from `~/.hermes/.env`):
   ```
   python "%DC_REPO%\integrations\hermes\capture_to_dc.py" <path1> <path2> ...
   ```
   (PowerShell: use `$env:DC_REPO`. The python must have `requests` + `pillow`.)
4. The script prints ONE status line to stdout. Reply with that line **verbatim** — do not embellish it:
   - `Scheduled: <title> - $<price> - live <time> (job <id>). Reply 'cancel last' to undo.`
   - `Captured & scheduled for <time> (job <id>), still analyzing - title/price pending. ...`
   - `Couldn't analyze ...` / `Draft Commander is offline. ...`
5. Remember the most recent `job <id>` from a success line — needed for "cancel last".

## Cancel last
1. Recall the most recent `job_id` from the prior status line.
2. `terminal`: `curl -X POST "%DC_API_BASE%/api/jobs/<job_id>/cancel"`
3. On `{"success": true}` reply "Cancelled <job_id>."; otherwise relay the error.

## Common Pitfalls
1. Listing a photo that wasn't meant to sell — require the "sell" caption every time.
2. Splitting one item across messages — each message is a separate item; put all of an item's photos in one captioned message.
3. Paraphrasing the script output into a stronger claim — send the actual stdout line ("still analyzing" is NOT "Scheduled").
4. DC not running — the script returns an offline message; start DC (`python backend/wsgi.py`), photos aren't lost.
5. More than 12 photos — eBay caps at 12; the script keeps the first 12 (cover = first photo) and warns.

## Verification Checklist
- [ ] A photo captioned "sell" in the self-chat yields a status line with a `job <id>`.
- [ ] A photo with NO "sell" caption is ignored by this skill.
- [ ] The reply matches the script's stdout exactly.
- [ ] "cancel last" removes the most recent scheduled item (gone from Seller Hub).
