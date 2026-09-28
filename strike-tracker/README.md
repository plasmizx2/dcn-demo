# Strike Tracker

Paste in a list of names; anyone with the link can add or remove strikes. Shows a running count per person and a log of recent changes (with an optional reason). The page auto-refreshes every 5 seconds so everyone sees the same numbers.

- `/` — give or remove strikes, add names
- `/leaderboard` — who has the most and fewest strikes, plus a full ranking (ties share a rank)

## Run locally

```bash
cd strike-tracker
pip install -r requirements.txt
python app.py        # http://localhost:5000  (uses a local strikes.db SQLite file)
```

## Deploy on Render

**Option A: Blueprint (easiest)**
1. Move `render.yaml` to the repo root (Render only reads blueprints from the root), then push.
2. In Render: **New → Blueprint**, pick this repo. It creates the web service and a Postgres database and wires `DATABASE_URL` up.

**Option B: Manual**
1. **New → PostgreSQL** (free). Copy its *Internal Database URL*.
2. **New → Web Service**, pick this repo:
   - Root Directory: `strike-tracker`
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Env var `DATABASE_URL` = the URL from step 1
3. Open the service URL, expand **Add names**, and paste your list.

> Use Postgres on Render. The free web service's disk gets wiped on every deploy/restart, so the SQLite fallback would lose all strikes.
> Note: Render's free Postgres expires after 30 days. Upgrade it if you need to keep data longer.

## Render's free plan sleeping

A free Render web service goes to sleep after ~15 minutes idle and takes ~30–60s to wake up. Two things handle that:

1. **No lost clicks.** Every +/− is saved in the browser first and resent automatically (with backoff) until the server confirms it, even after a page reload. Each click has a unique id, so a resend is never counted twice. A `*` next to a count means it's still sending.
2. **Keep it awake (recommended).** Point a free uptime pinger such as [UptimeRobot](https://uptimerobot.com) or [cron-job.org](https://cron-job.org) at `https://<your-app>.onrender.com/healthz` every 5–10 minutes. One always-on service fits within Render's 750 free hours/month. You can also upgrade to the $7 Starter plan, which never sleeps.

Note: the page itself is also served by the sleeping service, so the very first visit after a nap still waits for the wake-up. The pinger in step 2 avoids that.

## Optional: lock the name list

Set the env var `ADMIN_KEY` to any secret. Then adding or deleting *people* asks for that key, while adding/removing *strikes* stays open to everyone.
