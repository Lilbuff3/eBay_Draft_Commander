"""Hermes -> Draft Commander capture bridge.

Invoked by the Hermes 'ebay-capture' skill with the inbound photo paths for ONE item.
Normalizes images to ordered JPEGs, writes them to DC's captures dir, POSTs /api/capture,
polls the job to completion, and returns a WhatsApp-ready status line.
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
    resp = requests.post(f"{api_base}/api/capture", json={'path': folder}, timeout=30)
    if resp.status_code != 200 or not resp.json().get('success'):
        return f"Capture failed: {resp.status_code} {resp.text[:200]}"
    job_id = resp.json()['job_id']

    deadline = time.time() + poll_timeout
    last = {}
    while time.time() < deadline:
        g = requests.get(f"{api_base}/api/jobs/{job_id}", timeout=15)
        if g.status_code == 200:
            last = g.json()
            if str(last.get('status')) in TERMINAL_STATUSES:
                break
        time.sleep(poll_interval)

    status = str(last.get('status'))
    if status == 'failed':
        return f"Couldn't analyze the item (job {job_id}). Bad photos? Nothing scheduled."
    title = last.get('user_title') or last.get('title') or '(untitled)'
    price = last.get('price') or last.get('user_price') or '?'
    when = last.get('scheduled_time') or resp.json().get('scheduled_time')
    return f"{prefix_warn}Scheduled: {title} - ${price} - live {when} (job {job_id}). Reply 'cancel last' to undo."


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(capture(sys.argv[1:]))
