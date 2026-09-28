# Strike Tracker

Paste in a list of names; anyone can add or remove strikes, from the website **or from Discord buttons**. 100% free: Render's free web plan + a Discord channel as the storage. No database to set up.

- `/`: give or remove strikes, add names, see recent activity
- `/leaderboard`: most / fewest strikes and a full ranking
- In Discord: type `/strikes` → pick a name → **➕ Add strike**, **📝 Add with reason**, or **➖ Remove strike**

## How the data is stored (the Discord trick)

Render's free plan wipes the disk every time the app restarts. So the app:

1. Works from a local SQLite file while running.
2. After every change, edits **one message** in your Discord channel. That message shows a leaderboard and has the real data attached as `strikes.json`. **Don't delete that message.** (If you do, the app just makes a new one from what it has.)
3. On startup, downloads that `strikes.json` and restores everything.
4. Posts each strike in the channel (`🟥 Bob got a strike → 2 — late · by sean`), so the chat is also the history.

Tip: make a dedicated channel (e.g. `#strikes`) and pin the leaderboard message.

## Setup

### 1. Discord webhook (required: this is the storage)
Discord → your channel → ⚙️ **Edit Channel → Integrations → Webhooks → New Webhook** → **Copy Webhook URL**.

### 2. Deploy on Render (free)
**New → Web Service** → connect this repo:
- Root Directory: `strike-tracker`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --workers 1 --threads 8 --timeout 60` (keep it at **1 worker**)
- Instance type: **Free**
- Environment variable: `DISCORD_WEBHOOK_URL` = the URL from step 1

Open the site, expand **Add names**, paste your list. The leaderboard message appears in Discord within a couple of seconds.

### 3. Discord buttons (optional)
1. Go to https://discord.com/developers/applications → **New Application**.
2. **General Information**: copy the **Public Key** → set `DISCORD_PUBLIC_KEY` on Render.
3. **Bot** tab → **Reset Token** → copy it → set `DISCORD_BOT_TOKEN` on Render. Let Render redeploy.
4. Back on **General Information**, set **Interactions Endpoint URL** to `https://<your-app>.onrender.com/discord/interactions` and save. Discord tests it right away, so the app must be awake: open the site first.
5. **Installation** tab → Guild Install scope `applications.commands` → open the install link → add it to your server.
6. In the channel, type `/strikes`.

### 4. Keep it awake (strongly recommended, also free)
Free Render services sleep after ~15 min idle and take ~30–60 s to wake. The website copes (clicks are queued in the browser and sent when it's back), but **Discord buttons time out after 3 seconds** and show "This interaction failed" if the app is asleep.

Fix: create a free monitor on [UptimeRobot](https://uptimerobot.com) or [cron-job.org](https://cron-job.org) that hits `https://<your-app>.onrender.com/healthz` every 5 minutes. One always-on service fits in Render's 750 free hours/month.

## Optional settings
| Env var | What it does |
|---|---|
| `ADMIN_KEY` | Require this password to add/delete *names* on the website. Strikes stay open to everyone. |
| `DISCORD_ANNOUNCE=0` | Don't post each strike in the channel (the leaderboard message still updates). |
| `DISCORD_STATE_MESSAGE_ID` | Force which message holds the data (normally found automatically). |

## Run locally
```bash
cd strike-tracker
pip install -r requirements.txt
python app.py        # http://localhost:5000 (Discord vars optional)
```
