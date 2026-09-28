"""Strike Tracker: paste a list of names, anyone can add or remove strikes.

Storage: Postgres when DATABASE_URL is set (use this on Render), otherwise a
local SQLite file (strikes.db) for development.

Optional: set ADMIN_KEY to require a key for adding/removing *people*.
Adding/removing *strikes* is always open to everyone.
"""

import os
import sqlite3
from contextlib import contextmanager

from flask import Flask, jsonify, request, send_from_directory

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
USE_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if USE_PG:
    import psycopg2

app = Flask(__name__, static_folder="static")


@contextmanager
def db():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "strikes.db"))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def run(conn, sql, params=()):
    """Execute SQL written with '?' placeholders on either backend."""
    if USE_PG:
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def init_db():
    serial = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    now = "CURRENT_TIMESTAMP"
    with db() as conn:
        run(conn, f"""CREATE TABLE IF NOT EXISTS people (
            id {serial},
            name TEXT NOT NULL UNIQUE,
            strikes INTEGER NOT NULL DEFAULT 0
        )""")
        run(conn, f"""CREATE TABLE IF NOT EXISTS log (
            id {serial},
            name TEXT NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            op_id TEXT UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT {now}
        )""")


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
        people = run(conn, "SELECT id, name, strikes FROM people ORDER BY strikes DESC, LOWER(name)").fetchall()
        log = run(conn, "SELECT name, delta, reason, created_at FROM log ORDER BY id DESC LIMIT 25").fetchall()
    return jsonify(
        people=[{"id": p[0], "name": p[1], "strikes": p[2]} for p in people],
        log=[{"name": l[0], "delta": l[1], "reason": l[2], "at": str(l[3])} for l in log],
        admin_required=bool(ADMIN_KEY),
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
            if run(conn, "SELECT 1 FROM people WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
                continue
            run(conn, "INSERT INTO people (name) VALUES (?)", (name,))
            added += 1
    return jsonify(added=added)


@app.delete("/api/people/<int:pid>")
def delete_person(pid):
    if (err := check_admin()):
        return err
    with db() as conn:
        run(conn, "DELETE FROM people WHERE id = ?", (pid,))
    return jsonify(ok=True)


@app.post("/api/people/<int:pid>/strike")
def change_strike(pid):
    body = request.get_json(silent=True) or {}
    delta = 1 if body.get("delta", 1) >= 0 else -1
    reason = (body.get("reason") or "").strip()[:200] or None
    # Client-generated id so a click that gets resent (e.g. while Render is
    # waking up) is only ever applied once.
    op_id = str(body.get("op_id") or "")[:64] or None
    with db() as conn:
        if op_id and run(conn, "SELECT 1 FROM log WHERE op_id = ?", (op_id,)).fetchone():
            return jsonify(ok=True, duplicate=True)
        row = run(conn, "SELECT name, strikes FROM people WHERE id = ?", (pid,)).fetchone()
        if not row:
            # Person was deleted; tell the client to drop this click instead of retrying.
            return jsonify(ok=True, skipped="Person no longer exists")
        if delta < 0 and row[1] <= 0:
            return jsonify(ok=True, skipped=f"{row[0]} has no strikes to remove")
        # Atomic update so simultaneous clicks don't overwrite each other.
        run(conn, "UPDATE people SET strikes = CASE WHEN strikes + ? < 0 THEN 0 ELSE strikes + ? END WHERE id = ?",
            (delta, delta, pid))
        run(conn, "INSERT INTO log (name, delta, reason, op_id) VALUES (?, ?, ?, ?)",
            (row[0], delta, reason, op_id))
        strikes = run(conn, "SELECT strikes FROM people WHERE id = ?", (pid,)).fetchone()[0]
    return jsonify(strikes=strikes)


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
