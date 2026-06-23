"""Hermes -> Draft Commander capture bridge.

Invoked by the Hermes 'ebay-capture' plugin (pre_gateway_dispatch hook) with the inbound
photo paths for ONE item, or with --cancel to undo the last capture. Normalizes images to
ordered JPEGs, writes them to DC's captures dir, POSTs /api/capture, polls the job, and
returns a WhatsApp-ready status line (also posted back to the chat via --chat-id).
"""
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image

DEFAULT_API_BASE = os.environ.get('DC_API_BASE', 'http://127.0.0.1:5000')
DEFAULT_CAPTURES_DIR = os.environ.get('DC_CAPTURES_DIR', '')
TERMINAL_STATUSES = {'scheduled', 'completed', 'failed'}


def build_item_folder(image_paths, captures_dir):
    """Normalize images to RGB JPEG, write as 01.jpg.. in given order. Returns folder path."""
    folder = Path(captures_dir) / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=True)
    saved = 0
    for idx, src in enumerate(image_paths, start=1):
        try:
            img = Image.open(src).convert('RGB')
        except Exception as e:  # HEIC/unreadable: skip, keep going
            print(f"skip {src}: {e}", file=sys.stderr)
            continue
        img.save(folder / f"{idx:02d}.jpg", 'JPEG', quality=90)
        saved += 1
    if saved == 0:
        try:
            folder.rmdir()  # don't leave an empty folder behind
        except OSError:
            pass
        raise ValueError("No readable images")
    return str(folder)


def _health_ok(api_base):
    try:
        r = requests.get(f"{api_base}/api/system/health", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def capture(image_paths, api_base=None, captures_dir=None, poll_interval=3, poll_timeout=300):
    api_base = api_base or DEFAULT_API_BASE
    captures_dir = captures_dir or DEFAULT_CAPTURES_DIR
    if not captures_dir:
        return "DC_CAPTURES_DIR not configured - cannot capture."
    if not _health_ok(api_base):
        return "Draft Commander is offline. Photos kept; resend when it's running."

    prefix_warn = ""
    if len(image_paths) > 12:
        extra = len(image_paths) - 12
        image_paths = image_paths[:12]
        prefix_warn = f"(warning: {extra} extra photo(s) dropped - eBay max 12) "

    folder = build_item_folder(image_paths, captures_dir)
    try:
        resp = requests.post(f"{api_base}/api/capture", json={'path': folder}, timeout=30)
    except requests.RequestException as e:
        return f"Capture request failed: {e}"
    if resp.status_code != 200 or not resp.json().get('success'):
        return f"Capture failed: {resp.status_code} {resp.text[:200]}"
    job_id = resp.json()['job_id']
    try:
        (Path(captures_dir) / '.last_job').write_text(job_id, encoding='utf-8')
    except OSError:
        pass

    deadline = time.time() + poll_timeout
    last = {}
    while time.time() < deadline:
        try:
            g = requests.get(f"{api_base}/api/job/{job_id}/details", timeout=15)
        except requests.RequestException:
            time.sleep(poll_interval)
            continue
        if g.status_code == 200:
            last = g.json()
            if str(last.get('status', '')).lower() in TERMINAL_STATUSES:
                break
        time.sleep(poll_interval)

    status = str(last.get('status', '')).lower()
    when = last.get('scheduled_time') or resp.json().get('scheduled_time')
    if status == 'failed':
        return f"Couldn't analyze the item (job {job_id}). Bad photos? Nothing scheduled."
    if status not in TERMINAL_STATUSES:
        # Poll window elapsed before analysis finished. The slot was already assigned
        # at capture time, so the item IS scheduled — just title/price aren't final yet.
        return (f"{prefix_warn}Captured & scheduled for {when} (job {job_id}), "
                f"still analyzing - title/price pending. Check Draft Commander, or 'cancel last' to undo.")
    title = last.get('user_title') or last.get('ai_title') or '(untitled)'
    price = last.get('user_price') or last.get('suggested_price') or '?'
    return f"{prefix_warn}Scheduled: {title} - ${price} - live {when} (job {job_id}). Reply 'cancel last' to undo."


def send_whatsapp(message, chat_id, bridge_port=3000):
    """Reply into the WhatsApp chat via the local Hermes bridge /send endpoint."""
    try:
        requests.post(f"http://127.0.0.1:{bridge_port}/send",
                      json={'chatId': chat_id, 'message': message}, timeout=15)
    except requests.RequestException as e:
        print(f"send_whatsapp failed: {e}", file=sys.stderr)


def cancel_last(api_base=None, captures_dir=None):
    """Cancel the most recently captured job, read from <captures_dir>/.last_job."""
    api_base = api_base or DEFAULT_API_BASE
    captures_dir = captures_dir or DEFAULT_CAPTURES_DIR
    marker = (Path(captures_dir) / '.last_job') if captures_dir else None
    if not marker or not marker.exists():
        return "Nothing to cancel."
    job_id = marker.read_text(encoding='utf-8').strip()
    if not job_id:
        return "Nothing to cancel."
    try:
        r = requests.post(f"{api_base}/api/jobs/{job_id}/cancel", timeout=30)
    except requests.RequestException as e:
        return f"Cancel request failed: {e}"
    if r.status_code == 200 and r.json().get('success'):
        try:
            marker.unlink()
        except OSError:
            pass
        return f"Cancelled {job_id}."
    return f"Cancel failed for {job_id}: {r.status_code} {r.text[:160]}"


def collect_and_capture(chat_id, api_base=None, captures_dir=None, debounce=3.0):
    """Flush a chat's buffered photos (written by the Hermes plugin) into one listing.

    WhatsApp delivers an album as separate messages, so the plugin stages each photo
    under <captures>/.pending/<chat_id>/. We wait `debounce` seconds for any trailing
    album frames to land, then capture all staged photos as a single item and clear
    the buffer."""
    import re as _re
    api_base = api_base or DEFAULT_API_BASE
    captures_dir = captures_dir or DEFAULT_CAPTURES_DIR
    if not captures_dir:
        return "DC_CAPTURES_DIR not configured - cannot capture."
    safe = _re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    staging = Path(captures_dir) / ".pending" / safe
    time.sleep(debounce)  # let trailing album frames arrive before we gather
    if not staging.is_dir():
        return "No photos found to list."
    paths = sorted(str(p) for p in staging.iterdir() if p.is_file())
    if not paths:
        return "No photos found to list."
    try:
        return capture(paths, api_base=api_base, captures_dir=captures_dir)
    finally:
        import shutil as _sh
        _sh.rmtree(staging, ignore_errors=True)  # clear the buffer regardless of outcome


if __name__ == '__main__':
    import argparse
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Hermes -> Draft Commander eBay capture bridge")
    parser.add_argument('images', nargs='*', help="image file paths for ONE item")
    parser.add_argument('--chat-id', default=None, help="WhatsApp chat id to reply into")
    parser.add_argument('--bridge-port', default='3000', help="Hermes WhatsApp bridge port")
    parser.add_argument('--cancel', action='store_true', help="cancel the last captured listing")
    parser.add_argument('--collect', default=None, metavar='CHAT_ID',
                        help="flush this chat's buffered photos into one listing")
    args = parser.parse_args()

    def reply(msg):
        print(msg)
        if args.chat_id:
            send_whatsapp(msg, args.chat_id, args.bridge_port)

    if args.cancel:
        reply(cancel_last())
    elif args.collect:
        if args.chat_id:  # immediate ack while the album finishes arriving + analysis runs
            send_whatsapp("Got it - capturing & scheduling your listing...", args.chat_id, args.bridge_port)
        reply(collect_and_capture(args.collect))
    elif not args.images:
        reply("No images provided.")
    else:
        if args.chat_id:  # immediate ack so the user isn't left hanging during analysis
            send_whatsapp("Got it - capturing & scheduling your listing...", args.chat_id, args.bridge_port)
        reply(capture(args.images))
