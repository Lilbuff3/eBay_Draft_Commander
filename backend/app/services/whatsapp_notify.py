"""
WhatsApp (Hermes) back-channel notifications.

When a job originates from the Hermes WhatsApp bridge, its metadata carries an
``origin`` block ({channel:'whatsapp', chat_id, bridge_port}). This module lets
the backend push a message back into that chat via the Hermes bridge ``/send``
endpoint — the same endpoint the capture bridge already uses.

Used by the "auto-decide + tell me" flow: instead of stranding a WhatsApp item
in a pending_review queue the user never opens, the pipeline makes a sensible
default decision and reports it here.

Everything is best-effort: a messaging failure must NEVER affect a listing.
"""
from typing import Any, Dict, Optional

import requests

from backend.app.core.logger import get_logger

logger = get_logger('whatsapp_notify')

DEFAULT_BRIDGE_PORT = 3000


def get_whatsapp_origin(job_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the WhatsApp origin dict if this job came from the Hermes bridge
    and carries a usable chat_id; else None (e.g. web-UI jobs)."""
    if not job_metadata:
        return None
    origin = job_metadata.get('origin')
    if not isinstance(origin, dict):
        return None
    if origin.get('channel') != 'whatsapp' or not origin.get('chat_id'):
        return None
    return origin


def notify_whatsapp(origin: Optional[Dict[str, Any]], message: str) -> bool:
    """Best-effort push `message` to the originating WhatsApp chat via the Hermes
    bridge /send endpoint. Never raises. Returns True only on a 2xx response."""
    try:
        if not origin or not origin.get('chat_id') or not message:
            return False
        port = origin.get('bridge_port') or DEFAULT_BRIDGE_PORT
        resp = requests.post(
            f"http://127.0.0.1:{port}/send",
            json={'chatId': origin['chat_id'], 'message': message},
            timeout=10,
        )
        ok = 200 <= resp.status_code < 300
        if not ok:
            logger.warning(f"WhatsApp notify non-2xx ({resp.status_code}); message not delivered")
        return ok
    except Exception as e:
        logger.warning(f"WhatsApp notify failed (non-fatal): {e}")
        return False


def build_duplicate_message(title: Optional[str], dup_label: Optional[str]) -> str:
    name = title or 'your item'
    where = f" (listing {dup_label})" if dup_label else ""
    return (f"Skipped \"{name}\" - it looks like a duplicate of a recent listing{where}, "
            f"so it was not listed again. Re-send if that was intentional.")


def build_price_message(title: Optional[str], price: Any, review_reason: Optional[str]) -> str:
    name = title or 'your item'
    try:
        price_str = f"${float(price):.2f}"
    except (TypeError, ValueError):
        price_str = f"${price}"
    detail = f" ({review_reason})" if review_reason else ""
    return (f"Listing \"{name}\" at {price_str} despite a price flag{detail}. "
            f"Fix the price in the eBay app if it's off.")
