"""Use a Discord channel webhook as free, durable storage.

Render's free disk is wiped on every restart/deploy, so the app keeps its
working data in SQLite and mirrors a snapshot to Discord:

- One "state message" in the channel is edited after every change. Its text
  is a readable leaderboard; the attached strikes.json is the real data.
- On startup the app downloads that JSON and restores from it.
- Each strike is also announced in the channel as a running history.

Only a webhook URL is needed (no bot). The state message's id is remembered by
renaming the webhook to "strikes-state-<message id>"; posts still display as
"Strike Tracker" because each post overrides the username.
"""

import json
import logging
import os
import threading
import time

import requests

log = logging.getLogger("strike-tracker")

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").split("?")[0].rstrip("/")
ANNOUNCE = os.environ.get("DISCORD_ANNOUNCE", "1") != "0"
NAME_PREFIX = "strikes-state-"
DISPLAY_NAME = "Strike Tracker"
NO_PINGS = {"parse": []}  # never let a name like "@everyone" ping anyone
SAVE_DELAY = 2  # seconds; batches rapid clicks into one edit (Discord rate limits)

enabled = bool(WEBHOOK)


def _req(method, url, **kw):
    """HTTP call that waits out Discord 429 rate limits."""
    for _ in range(5):
        r = requests.request(method, url, timeout=15, **kw)
        if r.status_code != 429:
            return r
        time.sleep(float(r.json().get("retry_after", 1)) + 0.1)
    return r


def esc(text):
    """Escape Discord markdown so names show literally."""
    for ch in "\\*_~`|>#-[]()":
        text = text.replace(ch, "\\" + ch)
    return text


def _state_message_id():
    mid = os.environ.get("DISCORD_STATE_MESSAGE_ID")
    if mid:
        return mid
    r = _req("GET", WEBHOOK)
    r.raise_for_status()
    name = r.json().get("name") or ""
    return name[len(NAME_PREFIX):] if name.startswith(NAME_PREFIX) else None


def load():
    """Return the last saved snapshot dict, or None if nothing was saved yet.

    Raises on network/Discord errors so the caller can retry instead of
    starting empty and overwriting the backup.
    """
    mid = _state_message_id()
    if not mid:
        return None
    r = _req("GET", f"{WEBHOOK}/messages/{mid}")
    if r.status_code == 404:
        log.warning("Discord state message %s is gone; starting fresh", mid)
        return None
    r.raise_for_status()
    att = [a for a in r.json().get("attachments", []) if a.get("filename") == "strikes.json"]
    if not att:
        return None
    f = requests.get(att[0]["url"], timeout=15)
    f.raise_for_status()
    return f.json()


def _leaderboard_text(snapshot):
    people = sorted(snapshot["people"], key=lambda p: (-p["strikes"], p["name"].lower()))
    lines = ["**Strike leaderboard**"]
    for i, p in enumerate(people[:40], 1):
        lines.append(f"{i}. {esc(p['name'])} — **{p['strikes']}**")
    if len(people) > 40:
        lines.append(f"…and {len(people) - 40} more")
    lines.append(f"-# updated <t:{int(time.time())}:R> · don't delete this message, it stores the data")
    text = "\n".join(lines)
    return text if len(text) <= 2000 else text[:1990] + "\n…"


class Syncer:
    """Debounced background uploader for snapshots and announcements."""

    def __init__(self, snapshot_fn):
        self.snapshot_fn = snapshot_fn
        self.dirty = threading.Event()
        self.flush_lock = threading.Lock()
        self.lines_lock = threading.Lock()
        self.lines = []
        self.mid = None
        self.last_error = None
        self.last_saved = None
        threading.Thread(target=self._loop, daemon=True).start()

    def mark_dirty(self, announcement=None):
        if announcement and ANNOUNCE:
            with self.lines_lock:
                self.lines.append(announcement)
        self.dirty.set()

    def _loop(self):
        while True:
            self.dirty.wait()
            time.sleep(SAVE_DELAY)
            if not self.flush():
                time.sleep(5)

    def flush(self):
        """Upload pending announcements and the current snapshot. Returns success."""
        with self.flush_lock:
            self.dirty.clear()
            with self.lines_lock:
                lines, self.lines = self.lines, []
            try:
                self._announce(lines)
                lines = []
                self._save(self.snapshot_fn())
                self.last_error, self.last_saved = None, time.time()
                return True
            except Exception as e:  # keep the app running; retry on next loop
                log.exception("Discord sync failed")
                self.last_error = str(e)[:200]
                with self.lines_lock:
                    self.lines = lines + self.lines
                self.dirty.set()
                return False

    def _announce(self, lines):
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1900:
                self._post(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            self._post(chunk)

    def _post(self, content):
        r = _req("POST", WEBHOOK, json={"content": content, "username": DISPLAY_NAME, "allowed_mentions": NO_PINGS})
        r.raise_for_status()

    def _save(self, snapshot):
        payload = {
            "content": _leaderboard_text(snapshot),
            "allowed_mentions": NO_PINGS,
            "attachments": [{"id": 0, "filename": "strikes.json"}],
        }
        files = {"files[0]": ("strikes.json", json.dumps(snapshot).encode(), "application/json")}
        if self.mid is None:
            self.mid = _state_message_id()
        if self.mid:
            r = _req("PATCH", f"{WEBHOOK}/messages/{self.mid}", data={"payload_json": json.dumps(payload)}, files=files)
            if r.status_code != 404:
                r.raise_for_status()
                return
            log.warning("Discord state message was deleted; creating a new one")
        payload["username"] = DISPLAY_NAME
        r = _req("POST", f"{WEBHOOK}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
        r.raise_for_status()
        self.mid = r.json()["id"]
        # Remember the message id in the webhook's own name so no manual setup is needed.
        rn = _req("PATCH", WEBHOOK, json={"name": NAME_PREFIX + self.mid})
        if not rn.ok:
            log.warning("Couldn't rename webhook; set DISCORD_STATE_MESSAGE_ID=%s instead", self.mid)
