"""Strike Tracker: paste a list of names, anyone can add or remove strikes.

Everything is free:
- Data lives in a local SQLite file (strikes.db).
- If DISCORD_WEBHOOK_URL is set, every change is backed up to a Discord
  channel and restored from there on startup (Render's free disk is wiped on
  each restart). See discord_store.py.
- If DISCORD_PUBLIC_KEY and DISCORD_BOT_TOKEN are set, the /strikes slash
  command gives a name picker with add/remove buttons inside Discord. See
  discord_bot.py.

Optional: set ADMIN_KEY to require a key for adding/removing *people*.
Adding/removing *strikes* is always open to everyone.
"""

import atexit
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

from flask import Flask, jsonify, request, send_from_directory

import discord_bot
import discord_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("strike-tracker")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "strikes.db"))
LOG_KEEP = 300  # log rows kept in the Discord snapshot (also used for resend dedupe)

app = Flask(__name__, static_folder="static")
ready = threading.Event()  # set once the Discord backup has been restored


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            strikes INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            op_id TEXT UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


def snapshot():
    with db() as conn:
        people = conn.execute("SELECT id, name, strikes FROM people ORDER BY id").fetchall()
        rows = conn.execute("SELECT id, name, delta, reason, op_id, created_at FROM log ORDER BY id DESC LIMIT ?",
                            (LOG_KEEP,)).fetchall()
    return {
        "version": 1,
        "people": [{"id": p[0], "name": p[1], "strikes": p[2]} for p in people],
        "log": [dict(zip(("id", "name", "delta", "reason", "op_id", "at"), r)) for r in reversed(rows)],
    }


def restore(snap):
    # Keep the same ids so strikes queued in people's browsers still hit the right person.
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]:
            return  # local data already present (e.g. running locally); don't clobber it
        conn.executemany("INSERT INTO people (id, name, strikes) VALUES (?, ?, ?)",
                         [(p["id"], p["name"], p["strikes"]) for p in snap.get("people", [])])
        conn.executemany("INSERT INTO log (id, name, delta, reason, op_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         [(l["id"], l["name"], l["delta"], l["reason"], l["op_id"], l["at"]) for l in snap.get("log", [])])
    log.info("Restored %d people from Discord", len(snap.get("people", [])))


syncer = discord_store.Syncer(snapshot) if discord_store.enabled else None


def changed(announcement=None):
    if syncer:
        syncer.mark_dirty(announcement)


def startup():
    """Restore from Discord before accepting writes, retrying until it works.

    Starting empty and saving would overwrite the backup, so the API answers
    503 until this finishes; browsers keep their clicks queued meanwhile.
    """
    while discord_store.enabled:
        try:
            snap = discord_store.load()
            if snap:
                restore(snap)
            break
        except Exception:
            log.exception("Couldn't load Discord backup; retrying in 5s")
            time.sleep(5)
    ready.set()
    discord_bot.register_commands()


# ---------------------------------------------------------------- core logic

def apply_strike(pid, delta, reason=None, op_id=None, by=None):
    """Add (+1) or remove (-1) a strike. Returns a dict describing the result."""
    delta = 1 if delta >= 0 else -1
    reason = (reason or "").strip()[:200] or None
    with db() as conn:
        # op_id makes resends (from browsers retrying while Render wakes up) count once.
        if op_id and conn.execute("SELECT 1 FROM log WHERE op_id = ?", (op_id,)).fetchone():
            return {"ok": True, "duplicate": True}
        row = conn.execute("SELECT name, strikes FROM people WHERE id = ?", (pid,)).fetchone()
        if not row:
            return {"ok": True, "skipped": "Person no longer exists"}
        name = row[0]
        if delta < 0 and row[1] <= 0:
            return {"ok": True, "name": name, "strikes": 0, "skipped": f"{name} has no strikes to remove"}
        conn.execute("UPDATE people SET strikes = MAX(strikes + ?, 0) WHERE id = ?", (delta, pid))
        conn.execute("INSERT INTO log (name, delta, reason, op_id) VALUES (?, ?, ?, ?)", (name, delta, reason, op_id))
        strikes = conn.execute("SELECT strikes FROM people WHERE id = ?", (pid,)).fetchone()[0]
    icon, verb = ("🟥", "got a strike") if delta > 0 else ("🟩", "had a strike removed")
    line = f"{icon} **{discord_store.esc(name)}** {verb} → **{strikes}**"
    if reason:
        line += f" — {discord_store.esc(reason)}"
    line += f" · by {discord_store.esc(by)}" if by else " · via website"
    changed(line)
    return {"ok": True, "name": name, "strikes": strikes}


def list_people_rows():
    with db() as conn:
        return conn.execute("SELECT id, name, strikes FROM people ORDER BY LOWER(name)").fetchall()


# ------------------------------------------------------------------- routes

@app.before_request
def wait_for_restore():
    if request.path.startswith("/api/") and not ready.is_set():
        return jsonify(error="Starting up, loading data from Discord…"), 503


def check_admin():
    if ADMIN_KEY and request.headers.get("X-Admin-Key", "") != ADMIN_KEY:
        return jsonify(error="Wrong or missing admin key"), 403
    return None


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/leaderboard")
def leaderboard():
    return send_from_directory(app.static_folder, "leaderboard.html")


@app.get("/api/people")
def list_people():
    with db() as conn:
        people = conn.execute("SELECT id, name, strikes FROM people ORDER BY strikes DESC, LOWER(name)").fetchall()
        rows = conn.execute("SELECT name, delta, reason, created_at FROM log ORDER BY id DESC LIMIT 25").fetchall()
    backup = None
    if syncer:
        backup = {"error": syncer.last_error, "saved": syncer.last_saved}
    return jsonify(
        people=[{"id": p[0], "name": p[1], "strikes": p[2]} for p in people],
        log=[{"name": l[0], "delta": l[1], "reason": l[2], "at": str(l[3])} for l in rows],
        admin_required=bool(ADMIN_KEY),
        backup=backup,
    )


@app.post("/api/people")
def add_people():
    if (err := check_admin()):
        return err
    raw = (request.get_json(silent=True) or {}).get("names", "")
    # Accept one name per line and/or comma-separated.
    names = {n.strip() for chunk in raw.splitlines() for n in chunk.split(",")}
    names = sorted(n[:80] for n in names if n)
    added = 0
    with db() as conn:
        for name in names:
            if conn.execute("SELECT 1 FROM people WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
                continue
            conn.execute("INSERT INTO people (name) VALUES (?)", (name,))
            added += 1
    if added:
        changed()
    return jsonify(added=added)


@app.delete("/api/people/<int:pid>")
def delete_person(pid):
    if (err := check_admin()):
        return err
    with db() as conn:
        conn.execute("DELETE FROM people WHERE id = ?", (pid,))
    changed()
    return jsonify(ok=True)


@app.post("/api/people/<int:pid>/strike")
def change_strike(pid):
    body = request.get_json(silent=True) or {}
    try:
        delta = int(body.get("delta", 1))
    except (TypeError, ValueError):
        delta = 1
    return jsonify(apply_strike(pid, delta, body.get("reason"), str(body.get("op_id") or "")[:64] or None))


@app.post("/discord/interactions")
def discord_interactions():
    return discord_bot.handle(request, apply_strike, list_people_rows, ready)


@atexit.register
def final_flush():
    # Render stops idle free services; push any last unsaved change first.
    if syncer and syncer.dirty.is_set():
        syncer.flush()


init_db()
threading.Thread(target=startup, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
