"""Hermes 'ebay-capture' plugin.

Deterministic trigger for the eBay capture flow. Registers a ``pre_gateway_dispatch``
hook that fires on every inbound message BEFORE the LLM agent. When a WhatsApp message
has image attachment(s) AND its caption/text contains "sell", it launches the capture
bridge (which posts the listing to Draft Commander and replies in the chat) and returns
``{"action": "skip"}`` so the LLM never runs. "cancel last"/"undo last" undoes the most
recent capture. Everything else returns ``None`` and flows to the LLM as normal.

The hook callback is invoked synchronously on the gateway event loop, so it must not
block: it launches the bridge as a detached background process and returns immediately.
The background bridge does the slow capture+poll and sends the reply itself.
"""
import os
import sys
import subprocess


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

        # photo(s) + "sell" -> capture (detached; do NOT wait, keeps the gateway loop free)
        if media and "sell" in text:
            subprocess.Popen(
                [sys.executable, script, "--chat-id", chat_id, "--bridge-port", port, *media],
                creationflags=flags,
            )
            return {"action": "skip", "reason": "ebay capture launched"}

        # "cancel last" / "undo last" -> undo the most recent capture
        if text.strip() in ("cancel last", "undo last"):
            subprocess.Popen(
                [sys.executable, script, "--cancel", "--chat-id", chat_id, "--bridge-port", port],
                creationflags=flags,
            )
            return {"action": "skip", "reason": "ebay cancel launched"}

        return None  # not ours -> normal LLM handling

    ctx.register_hook("pre_gateway_dispatch", on_message)
