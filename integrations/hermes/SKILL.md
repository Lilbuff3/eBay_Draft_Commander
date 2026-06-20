---
name: ebay-capture
description: Use when a photo arrives in the dedicated eBay chat. Turns that message's photos into one eBay scheduled listing via Draft Commander, and supports "cancel last" to undo the most recent one.
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
Bridge incoming WhatsApp photos into eBay **scheduled** listings via Draft Commander (DC).
One message = one item. Only photos posted in the dedicated eBay chat are processed — photos
in any other chat are left to Hermes' other skills. DC runs the full AI pipeline and schedules
the listing into an eBay peak-traffic window; you review/edit it in eBay Seller Hub before it
goes live.

## When to Use
- A photo message arrives in the chat whose id equals `EBAY_CAPTURE_CHAT_ID` (from `~/.hermes/.env`).
- The user says "cancel last" / "undo last" in that chat.
- **Don't use for:** photos in any other chat — ignore them, they belong to other skills.

## Capture a new item
1. Confirm the message's channel id equals `EBAY_CAPTURE_CHAT_ID`. If it does not, do nothing.
2. Collect ALL image attachments of THIS message, in order, and resolve their on-disk paths.
3. Run the bridge via the `terminal` tool, passing the image paths as arguments
   (`DC_API_BASE` and `DC_CAPTURES_DIR` are read from the environment by the script):
   ```
   python "%DC_REPO%\integrations\hermes\capture_to_dc.py" <path1> <path2> ...
   ```
   (PowerShell: use `$env:DC_REPO`. The script needs `requests` + `pillow` importable —
   point it at DC's venv python if those aren't on the default interpreter.)
4. The script prints a single status line to stdout. Send that line back to the chat verbatim.
   It will be one of:
   - `Scheduled: <title> - $<price> - live <time> (job <id>). Reply 'cancel last' to undo.`
   - `Captured & scheduled for <time> (job <id>), still analyzing - title/price pending. ...`
   - `Couldn't analyze the item (job <id>). ...` / `Draft Commander is offline. ...`
5. Remember the most recent `job <id>` from a successful line — you'll need it for "cancel last".

## Cancel last
1. Recall the most recent `job_id` you captured in this chat (from the prior status line).
2. Run via `terminal`:
   ```
   curl -X POST "%DC_API_BASE%/api/jobs/<job_id>/cancel"
   ```
3. On `{"success": true}`, reply "Cancelled <job_id>." On failure, relay the error.

## Common Pitfalls
1. Processing photos from the wrong chat — only `EBAY_CAPTURE_CHAT_ID` is in scope.
2. Splitting one item across multiple messages — each message is a separate item.
3. Reporting "Scheduled" when the script returned the "still analyzing" line — send the
   actual stdout line; don't paraphrase it into a stronger claim.
4. DC not running — the script returns an offline message; tell the user to start DC, photos are not lost.
5. More than 12 photos in one message — eBay caps at 12; the script keeps the first 12 (cover = first) and warns.

## Verification Checklist
- [ ] A photo in the eBay chat yields a status line containing a `job <id>`.
- [ ] The reply matches the script's stdout exactly (no embellishment).
- [ ] "cancel last" removes the most recent scheduled item (Seller Hub no longer shows it).
- [ ] A photo in a different chat is ignored by this skill.
