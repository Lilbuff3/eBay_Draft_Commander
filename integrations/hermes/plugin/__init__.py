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


def _staging_dir(chat_id):
    """Per-chat photo buffer under <DC_CAPTURES_DIR>/.pending/<safe chat id>."""
    captures = os.environ.get("DC_CAPTURES_DIR", "")
    if not captures:
        return None
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    return os.path.join(captures, ".pending", safe)


def register(ctx):
    def on_message(event=None, gateway=None, session_store=None, **kwargs):
        text = (getattr(event, "text", "") or "").lower()
        media = list(getattr(event, "media_urls", None) or [])
        chat_id = getattr(getattr(event, "source", None), "chat_id", None)
        if not chat_id:
            return None

        repo = os.environ.get("DC_REPO", r"C:\Users\adam\Projects\ebay-draft-commander")
        script = os.path.join(repo, "integrations", "hermes", "capture_to_dc.py")
        port = os.environ.get("WHATSAPP_BRIDGE_PORT", "3000")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flash on Windows

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
            if staging and (staged_any or os.path.isdir(staging)):
                subprocess.Popen(
                    [sys.executable, script, "--collect", chat_id,
                     "--chat-id", chat_id, "--bridge-port", port],
                    creationflags=flags,
                )
            elif media:
                # Staging unavailable -> original single-message behavior.
                subprocess.Popen(
                    [sys.executable, script, "--chat-id", chat_id, "--bridge-port", port, *media],
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
