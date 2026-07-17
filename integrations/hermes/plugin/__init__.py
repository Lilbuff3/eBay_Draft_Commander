"""Hermes 'ebay-capture' plugin.

Deterministic trigger for the eBay capture flow. Registers a ``pre_gateway_dispatch``
hook that fires on every inbound message BEFORE the LLM agent.

Multi-photo aware: WhatsApp delivers a multi-photo "album" as SEPARATE messages, and
only one of them carries the caption. So every inbound photo is copied into a per-chat
staging folder; the message whose text contains "sell" flushes the whole staged set to
the capture bridge (which debounces briefly to catch trailing album frames). Buffered
photo messages return ``{"action": "skip"}`` so stray album frames never reach the LLM
(no "I'll stop what I'm doing" narration). "cancel last"/"undo last" undoes the most
recent capture. Plain text with no photo flows to the LLM as normal.

The hook callback is invoked synchronously on the gateway event loop, so it must not
block: copying a few small images is fast, and the slow capture+poll runs in a detached
background bridge process that replies to the chat itself.
"""
import os
import re
import sys
import time
import shutil
import subprocess


def _derive_note(text):
    """Caption minus the 'sell' trigger -> trusted seller note (may be empty).

    Removes 'sell' as a whole word (case-insensitive), collapses whitespace, trims.
    Residual filler is harmless — it's context for the AI, not shown verbatim.
    """
    if not text:
        return ""
    cleaned = re.sub(r"\bsell\b", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _staging_dir(chat_id):
    """Per-chat photo buffer under <DC_CAPTURES_DIR>/.pending/<safe chat id>."""
    captures = os.environ.get("DC_CAPTURES_DIR", "")
    if not captures:
        return None
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    return os.path.join(captures, ".pending", safe)


_REVIEW_OK_WORDS = ("ok", "okay", "yes", "approve")
_REVIEW_PRICE_RE = re.compile(r"^\$?(\d+(?:\.\d{1,2})?)$")


def _parse_review_reply(text):
    """'ok' | 'skip' | price-string | None. Mirrors the backend parser in
    backend/app/services/review_reply.py (kept dependency-free on purpose —
    this module runs inside the Hermes process)."""
    t = (text or "").strip().lower()
    if t in _REVIEW_OK_WORDS:
        return "ok"
    if t == "skip":
        return "skip"
    m = _REVIEW_PRICE_RE.match(t)
    if m:
        return m.group(1)
    return None


def _review_marker_exists(chat_id):
    """True when the backend has an outstanding price-review text for this
    chat (<DC_CAPTURES_DIR>/.review_pending/<safe chat id> is non-empty)."""
    captures = os.environ.get("DC_CAPTURES_DIR", "")
    if not captures:
        return False
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    path = os.path.join(captures, ".review_pending", safe)
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def register(ctx):
    def on_message(event=None, gateway=None, session_store=None, **kwargs):
        raw_text = getattr(event, "text", "") or ""
        text = raw_text.lower()
        media = list(getattr(event, "media_urls", None) or [])
        chat_id = getattr(getattr(event, "source", None), "chat_id", None)
        if not chat_id:
            return None

        repo = os.environ.get("DC_REPO", r"C:\Users\adam\Projects\ebay-draft-commander")
        script = os.path.join(repo, "integrations", "hermes", "capture_to_dc.py")
        port = os.environ.get("WHATSAPP_BRIDGE_PORT", "3000")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flash on Windows

        # Review-reply gate (additive): only fires when the backend has texted
        # a price review for THIS chat (marker file) and the message is a bare
        # ok/number/skip with no photo. Everything else falls through to the
        # pre-existing branches untouched.
        if not media:
            review_cmd = _parse_review_reply(raw_text)
            if review_cmd is not None and _review_marker_exists(chat_id):
                subprocess.Popen(
                    [sys.executable, script, "--review-reply", raw_text.strip(),
                     "--chat-id", chat_id, "--bridge-port", port],
                    creationflags=flags,
                )
                return {"action": "skip", "reason": "ebay review reply"}

        # Buffer every inbound photo into this chat's staging folder.
        staging = _staging_dir(chat_id)
        staged_any = False
        if media and staging:
            try:
                os.makedirs(staging, exist_ok=True)
                for src in media:
                    base = os.path.basename(str(src)) or "img"
                    dst = os.path.join(staging, f"{int(time.time() * 1000)}_{base}")
                    shutil.copyfile(src, dst)
                    staged_any = True
            except Exception:
                staged_any = False  # staging failed -> fall back to direct media below

        # "sell" -> flush the whole staged set (covers single + multi-photo albums)
        if "sell" in text:
            note = _derive_note(raw_text)
            note_args = ["--note", note] if note else []
            if staging and (staged_any or os.path.isdir(staging)):
                subprocess.Popen(
                    [sys.executable, script, "--collect", chat_id,
                     "--chat-id", chat_id, "--bridge-port", port, *note_args],
                    creationflags=flags,
                )
            elif media:
                # Staging unavailable -> original single-message behavior.
                subprocess.Popen(
                    [sys.executable, script, "--chat-id", chat_id, "--bridge-port", port, *note_args, *media],
                    creationflags=flags,
                )
            else:
                return None  # "sell" with no photo and nothing staged -> let LLM handle
            return {"action": "skip", "reason": "ebay capture launched"}

        # Photo(s) with no "sell" yet -> buffered, waiting for the trigger. Don't hit the LLM.
        if staged_any:
            return {"action": "skip", "reason": "ebay photo buffered"}

        # "cancel last" / "undo last" -> undo the most recent capture
        if text.strip() in ("cancel last", "undo last"):
            subprocess.Popen(
                [sys.executable, script, "--cancel", "--chat-id", chat_id, "--bridge-port", port],
                creationflags=flags,
            )
            return {"action": "skip", "reason": "ebay cancel launched"}

        return None  # not ours -> normal LLM handling

    ctx.register_hook("pre_gateway_dispatch", on_message)
