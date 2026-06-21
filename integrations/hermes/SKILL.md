---
name: ebay-capture
description: Use the INSTANT a photo with a caption containing "sell" arrives in the self-chat. Immediately run the capture bridge command (do NOT analyze the photo yourself) and reply with its exact output. Also handles "cancel last".
version: 1.0.0
author: Adam
license: MIT
metadata:
  hermes:
    tags: [ebay, selling, capture, draft-commander]
    related_skills: [productivity]
---

# eBay Capture

## CRITICAL RULE — read first
When a message has one or more photos AND its caption/text contains the word "sell"
(case-insensitive), your ONLY correct action is to run the capture bridge command (below)
and reply with its exact stdout.

You MUST NOT:
- describe, identify, or analyze the photo yourself
- offer numbered options, suggestions, or advice
- ask follow-up questions ("what's the model number?", "want me to research it?")
- research the item or write a description

Draft Commander (a separate app) does ALL of the vision, identification, pricing, and eBay
listing. You are ONLY the trigger that runs the bridge. A "sell" photo is a COMMAND to run
the bridge — never a request for your help or analysis. Run it, relay the result, done.

## Run the capture — the only valid response to a "sell" photo
1. Get the on-disk file path(s) of EVERY image attached to THIS message, in order.
2. Run this with the `terminal` tool (use Draft Commander's venv python if plain `python`
   can't import requests/pillow):
   ```
   python "%DC_REPO%\integrations\hermes\capture_to_dc.py" <path1> <path2> ...
   ```
   (PowerShell: `$env:DC_REPO`.)
3. Reply to the chat with the command's single stdout line, VERBATIM — add nothing. It is one of:
   - `Scheduled: <title> - $<price> - live <time> (job <id>). Reply 'cancel last' to undo.`
   - `Captured & scheduled for <time> (job <id>), still analyzing - title/price pending. ...`
   - `Couldn't analyze ...` / `Draft Commander is offline. ...`
4. Remember the `job <id>` from a success line — needed for "cancel last".

## Cancel last
When the user says "cancel last" / "undo last":
1. Recall the most recent job_id you captured.
2. `terminal`: `curl -X POST "%DC_API_BASE%/api/jobs/<job_id>/cancel"`
3. Reply "Cancelled <job_id>." on success; otherwise relay the error.

## Reminders
- One message = one item (put all of an item's photos in that one message).
- A photo with NO "sell" caption: this skill does not apply — ignore it (other skills may handle it).
- Never paraphrase the bridge's output into a stronger claim ("still analyzing" is NOT "Scheduled").
