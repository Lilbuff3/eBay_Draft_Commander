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


def get_notify_destination(job_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Where to text about this job: the originating WhatsApp chat if the job
    came from the Hermes bridge, else the owner chat configured in
    WHATSAPP_NOTIFY_CHAT_ID (empty setting = notifications off for web jobs)."""
    origin = get_whatsapp_origin(job_metadata)
    if origin:
        return origin
    try:
        from backend.app.core.settings_manager import get_settings_manager
        chat_id = (get_settings_manager().get('WHATSAPP_NOTIFY_CHAT_ID', '') or '').strip()
    except Exception as e:
        logger.warning(f"Could not read WHATSAPP_NOTIFY_CHAT_ID (non-fatal): {e}")
        chat_id = ''
    if not chat_id:
        return None
    return {'channel': 'whatsapp', 'chat_id': chat_id, 'bridge_port': DEFAULT_BRIDGE_PORT}


def _fmt_money(value: Any) -> Optional[str]:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return None


def build_price_review_message(title: Optional[str], price: Any,
                               comp_price: Any, ai_price: Any,
                               reason: Optional[str] = None) -> str:
    """Text for a job held in price review. Conflict form shows both numbers;
    plain form shows the held price + why."""
    name = title or 'your item'
    comp_s, ai_s = _fmt_money(comp_price), _fmt_money(ai_price)
    if comp_s and ai_s:
        return (f'Price check: "{name}" — comps say {comp_s} but AI research says {ai_s}. '
                f'Held for review with {ai_s} pre-filled; approve or adjust in the app.')
    price_s = _fmt_money(price) or f"${price}"
    detail = f" ({reason})" if reason else ""
    return (f'Price check: "{name}" at {price_s}{detail}. '
            f'Held for review; approve or adjust in the app.')


def build_queue_summary_message(listed_count: int, total_value: float,
                                review_count: int) -> str:
    """One-line end-of-queue digest."""
    parts = [f"{listed_count} listed (${total_value:,.2f} total)"]
    if review_count:
        parts.append(f"{review_count} held for price review")
    return "Queue done: " + ", ".join(parts) + "."
