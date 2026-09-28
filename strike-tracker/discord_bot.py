"""Discord buttons: /strikes -> pick a name -> Add / Remove strike.

Uses Discord's HTTP "Interactions Endpoint URL", so no always-on bot process
is needed: Discord POSTs each click to /discord/interactions on this app.

Needs DISCORD_PUBLIC_KEY (to verify requests really come from Discord) and
DISCORD_BOT_TOKEN (only to register the /strikes command on startup).
"""

import json
import logging
import os

import requests
from flask import jsonify

log = logging.getLogger("strike-tracker")

PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "")  # set automatically by Render
API = "https://discord.com/api/v10"

# Interaction + response types (https://discord.com/developers/docs/interactions)
PING, COMMAND, COMPONENT, MODAL_SUBMIT = 1, 2, 3, 5
R_PONG, R_MESSAGE, R_UPDATE, R_MODAL = 1, 4, 7, 9
EPHEMERAL = 64  # only the person who clicked sees the reply

enabled = bool(PUBLIC_KEY)


def register_commands():
    if not BOT_TOKEN:
        return
    try:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        app_id = requests.get(f"{API}/applications/@me", headers=headers, timeout=15).json()["id"]
        r = requests.put(f"{API}/applications/{app_id}/commands", headers=headers, timeout=15,
                         json=[{"name": "strikes", "description": "Pick a name and add or remove a strike", "type": 1}])
        r.raise_for_status()
        log.info("Registered /strikes command")
    except Exception:
        log.exception("Couldn't register the /strikes Discord command")


def verify(req):
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey
    try:
        VerifyKey(bytes.fromhex(PUBLIC_KEY)).verify(
            req.headers.get("X-Signature-Timestamp", "").encode() + req.get_data(),
            bytes.fromhex(req.headers.get("X-Signature-Ed25519", "")),
        )
        return True
    except (BadSignatureError, ValueError):
        return False


def who(data):
    member = data.get("member") or {}
    user = member.get("user") or data.get("user") or {}
    return member.get("nick") or user.get("global_name") or user.get("username") or "someone"


def message(content, components=None, flags=EPHEMERAL, kind=R_MESSAGE):
    body = {"content": content, "components": components or [], "allowed_mentions": {"parse": []}}
    if flags:
        body["flags"] = flags
    return jsonify(type=kind, data=body)


def panel(people):
    """The public name picker: up to 5 dropdowns of 25 names each."""
    if not people:
        return message(f"No names yet. Add some on the website{': ' + SITE_URL if SITE_URL else ''}.")
    rows = []
    for i in range(0, min(len(people), 125), 25):
        chunk = people[i:i + 25]
        placeholder = "Pick a name" if len(people) <= 25 else f"Pick a name ({chunk[0][1][:20]} – {chunk[-1][1][:20]})"
        rows.append({"type": 1, "components": [{
            "type": 3, "custom_id": f"pick:{i}", "placeholder": placeholder[:150],
            "options": [{"label": name[:100], "value": str(pid)} for pid, name, _ in chunk],
        }]})
    text = "**Strikes:** pick a name to add or remove a strike."
    if SITE_URL:
        text += f"\nLeaderboard: {SITE_URL}/leaderboard"
    if len(people) > 125:
        text += f"\n-# Only the first 125 of {len(people)} names fit here; use the website for the rest."
    return message(text, rows, flags=0)


def card(pid, people, note=None, kind=R_MESSAGE):
    """The private add/remove buttons for one person."""
    person = next((p for p in people if p[0] == pid), None)
    if not person:
        return message("That person was removed from the list.", kind=kind)
    _, name, strikes = person
    text = f"**{name}** has **{strikes}** strike{'' if strikes == 1 else 's'}."
    if note:
        text += f"\n-# {note}"
    buttons = [{"type": 1, "components": [
        {"type": 2, "style": 4, "label": "Add strike", "emoji": {"name": "➕"}, "custom_id": f"add:{pid}"},
        {"type": 2, "style": 2, "label": "Add with reason", "emoji": {"name": "📝"}, "custom_id": f"why:{pid}"},
        {"type": 2, "style": 3, "label": "Remove strike", "emoji": {"name": "➖"}, "custom_id": f"sub:{pid}",
         "disabled": strikes == 0},
    ]}]
    return message(text, buttons, kind=kind)


def handle(req, apply_strike, list_people, ready):
    if not enabled:
        return jsonify(error="Discord bot not configured"), 404
    if not verify(req):
        return "invalid request signature", 401
    data = json.loads(req.get_data())
    kind = data.get("type")
    if kind == PING:
        return jsonify(type=R_PONG)
    if not ready.is_set():
        return message("Still starting up. Try again in a few seconds.")

    if kind == COMMAND:
        return panel(list_people())

    action, _, arg = (data.get("data", {}).get("custom_id") or "").partition(":")
    by = who(data)
    op_id = f"discord:{data.get('id')}"

    if kind == COMPONENT and action == "pick":
        pid = int(data["data"]["values"][0])
        return card(pid, list_people())

    if kind == COMPONENT and action in ("add", "sub"):
        pid = int(arg)
        res = apply_strike(pid, 1 if action == "add" else -1, op_id=op_id, by=by)
        note = res.get("skipped") or ("Strike added." if action == "add" else "Strike removed.")
        return card(pid, list_people(), note, kind=R_UPDATE)

    if kind == COMPONENT and action == "why":
        return jsonify(type=R_MODAL, data={
            "custom_id": f"reason:{arg}", "title": "Add a strike",
            "components": [{"type": 1, "components": [{
                "type": 4, "custom_id": "reason", "label": "Reason", "style": 2,
                "max_length": 200, "required": True,
            }]}],
        })

    if kind == MODAL_SUBMIT and action == "reason":
        pid = int(arg)
        reason = data["data"]["components"][0]["components"][0].get("value", "")
        res = apply_strike(pid, 1, reason=reason, op_id=op_id, by=by)
        return card(pid, list_people(), res.get("skipped") or "Strike added.", kind=R_UPDATE)

    return message("Unknown action.")
