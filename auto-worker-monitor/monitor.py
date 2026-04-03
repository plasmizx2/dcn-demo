#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCN Auto-Worker Monitor — lightweight GUI dashboard.
Shows what the auto-worker agent is doing in real time.

Usage:
    python monitor.py
    # Opens http://localhost:7890 in your browser
"""

import os
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

PORT = 7890
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LOG_FILE = os.path.join(BASE_DIR, "auto-worker.log")
STATE_FILE = os.path.join(BASE_DIR, ".auto-worker-state.json")


def read_log(tail=200):
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            return lines[-tail:]
    except FileNotFoundError:
        return ["No log file yet. The auto-worker hasn't run.\n"]


def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_cron_status():
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        if "auto-worker.sh" in result.stdout:
            return "active"
        return "not installed"
    except Exception:
        return "unknown"


def get_open_prs():
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--author", "@me", "--json", "number,title,headRefName,url,state,createdAt"],
            capture_output=True, text=True, timeout=10, cwd=BASE_DIR,
        )
        if result.returncode == 0:
            prs = json.loads(result.stdout)
            return [p for p in prs if p.get("headRefName", "").startswith("fix/issue-")]
        return []
    except Exception:
        return []


def get_issues():
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--json", "number,title,labels",
             "--jq", "sort_by(.number)"],
            capture_output=True, text=True, timeout=10, cwd=BASE_DIR,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return []
    except Exception:
        return []


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DCN Auto-Worker Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{--bg:#0c0e14;--surface:rgba(255,255,255,0.06);--border:rgba(255,255,255,0.10);--text:#f0f0f2;--muted:#b4b4bc;--dim:#8a8a96;--accent:#7c3aed;--accent2:#6366f1;--accent3:#3b82f6;--green:#22c55e;--red:#ef4444;--yellow:#eab308;--orange:#f97316}
  body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;min-height:100vh}

  .topbar{padding:20px 32px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
  .topbar h1{font-size:1.1rem;font-weight:800;letter-spacing:-0.5px}
  .topbar h1 span{background:linear-gradient(135deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .topbar-right{display:flex;align-items:center;gap:16px}
  .pill{padding:6px 14px;border-radius:20px;font-size:0.72rem;font-weight:600;border:1px solid var(--border);display:flex;align-items:center;gap:6px}
  .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
  .dot.green{background:var(--green);box-shadow:0 0 8px rgba(34,197,94,0.4)}
  .dot.yellow{background:var(--yellow);box-shadow:0 0 8px rgba(234,179,8,0.3)}
  .dot.red{background:var(--red);box-shadow:0 0 8px rgba(239,68,68,0.3)}
  .dot.blue{background:var(--accent3);box-shadow:0 0 8px rgba(59,130,246,0.3)}
  .dot.dim{background:var(--dim)}

  .grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:24px 32px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 24px}
  .card-label{font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin-bottom:14px}
  .full-width{grid-column:1/-1}

  .status-block{display:flex;flex-direction:column;gap:10px}
  .status-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
  .status-row:last-child{border:none}
  .status-key{font-size:0.78rem;color:var(--dim);font-weight:500}
  .status-val{font-size:0.82rem;font-weight:600}

  .issue-list{display:flex;flex-direction:column;gap:6px}
  .issue-row{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:8px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);font-size:0.78rem}
  .issue-num{font-weight:700;color:var(--accent3);min-width:32px}
  .issue-title{flex:1;color:var(--text)}
  .issue-label{padding:2px 8px;border-radius:10px;font-size:0.62rem;font-weight:600}
  .issue-label.P0{background:rgba(215,58,74,0.2);color:#f87171;border:1px solid rgba(215,58,74,0.3)}
  .issue-label.P1{background:rgba(233,150,149,0.15);color:#fca5a5;border:1px solid rgba(233,150,149,0.3)}
  .issue-label.P2{background:rgba(251,202,4,0.15);color:#fde047;border:1px solid rgba(251,202,4,0.3)}
  .issue-label.P3{background:rgba(14,138,22,0.15);color:#86efac;border:1px solid rgba(14,138,22,0.3)}

  .pr-row{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.15);font-size:0.78rem;margin-bottom:6px}
  .pr-num{font-weight:700;color:var(--accent)}
  .pr-title{flex:1}
  .pr-badge{padding:2px 10px;border-radius:10px;font-size:0.62rem;font-weight:600;background:rgba(34,197,94,0.15);color:var(--green);border:1px solid rgba(34,197,94,0.3)}

  .log-box{background:rgba(0,0,0,0.4);border:1px solid var(--border);border-radius:10px;padding:16px;font-family:'JetBrains Mono','SF Mono',monospace;font-size:0.72rem;line-height:1.8;max-height:500px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
  .log-box::-webkit-scrollbar{width:5px}
  .log-box::-webkit-scrollbar-track{background:transparent}
  .log-box::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}

  .log-line{padding:1px 0}
  .log-ts{color:#3f3f46}
  .log-skip{color:var(--yellow)}
  .log-wait{color:var(--orange)}
  .log-resume{color:var(--accent3)}
  .log-error{color:var(--red)}
  .log-done{color:var(--green)}
  .log-rate{color:var(--red)}

  .no-data{color:var(--dim);font-size:0.8rem;font-style:italic;padding:12px 0}

  @media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="topbar">
  <h1><span>DCN</span> Auto-Worker Monitor</h1>
  <div class="topbar-right">
    <div class="pill"><div class="dot" id="cronDot"></div><span id="cronStatus">Checking...</span></div>
    <div class="pill"><div class="dot" id="stateDot"></div><span id="stateStatus">Loading...</span></div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <div class="card-label">Agent Status</div>
    <div class="status-block" id="statusBlock">
      <div class="status-row"><span class="status-key">Cron Job</span><span class="status-val" id="cronVal">—</span></div>
      <div class="status-row"><span class="status-key">Current State</span><span class="status-val" id="stateVal">—</span></div>
      <div class="status-row"><span class="status-key">Working On</span><span class="status-val" id="workingOn">—</span></div>
      <div class="status-row"><span class="status-key">Branch</span><span class="status-val" id="branchVal">—</span></div>
      <div class="status-row"><span class="status-key">Last Log Entry</span><span class="status-val" id="lastLog">—</span></div>
    </div>
  </div>

  <div class="card">
    <div class="card-label">Open Pull Requests</div>
    <div id="prList"><div class="no-data">Loading...</div></div>
  </div>

  <div class="card full-width">
    <div class="card-label">Issue Queue</div>
    <div class="issue-list" id="issueList"><div class="no-data">Loading...</div></div>
  </div>

  <div class="card full-width">
    <div class="card-label">Activity Log</div>
    <div class="log-box" id="logBox">Loading...</div>
  </div>
</div>

<script>
async function fetchJSON(url) {
  const r = await fetch(url);
  return r.json();
}

function classifyLog(line) {
  if (line.includes('SKIP')) return 'log-skip';
  if (line.includes('WAIT')) return 'log-wait';
  if (line.includes('RESUME')) return 'log-resume';
  if (line.includes('ERROR')) return 'log-error';
  if (line.includes('Done with')) return 'log-done';
  if (line.includes('RATE LIMITED')) return 'log-rate';
  return '';
}

function priorityClass(labels) {
  for (const l of labels) {
    if (l.name.startsWith('P0')) return 'P0';
    if (l.name.startsWith('P1')) return 'P1';
    if (l.name.startsWith('P2')) return 'P2';
    if (l.name.startsWith('P3')) return 'P3';
  }
  return '';
}

async function refresh() {
  try {
    const data = await fetchJSON('/api/status');

    // Cron
    document.getElementById('cronVal').textContent = data.cron === 'active' ? 'Active (hourly)' : data.cron;
    const cronDot = document.getElementById('cronDot');
    cronDot.className = 'dot ' + (data.cron === 'active' ? 'green' : 'red');
    document.getElementById('cronStatus').textContent = data.cron === 'active' ? 'Cron Active' : 'Cron Off';

    // State
    const stateDot = document.getElementById('stateDot');
    if (data.state) {
      document.getElementById('stateVal').textContent = data.state.status;
      document.getElementById('workingOn').textContent = '#' + data.state.number + ' — ' + (data.state.title || '').substring(0, 50);
      document.getElementById('branchVal').textContent = data.state.branch;
      stateDot.className = 'dot blue';
      document.getElementById('stateStatus').textContent = 'Working';
    } else {
      document.getElementById('stateVal').textContent = 'Idle';
      document.getElementById('workingOn').textContent = 'Nothing — waiting for next cron run';
      document.getElementById('branchVal').textContent = '—';
      stateDot.className = 'dot dim';
      document.getElementById('stateStatus').textContent = 'Idle';
    }

    // Last log
    if (data.log_lines.length > 0) {
      document.getElementById('lastLog').textContent = data.log_lines[data.log_lines.length - 1].trim();
    }

    // Log box
    const logBox = document.getElementById('logBox');
    const wasAtBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
    logBox.innerHTML = data.log_lines.map(l => {
      const cls = classifyLog(l);
      const ts = l.match(/\\[.*?\\]/);
      if (ts) {
        const rest = l.substring(ts[0].length);
        return '<div class="log-line ' + cls + '"><span class="log-ts">' + ts[0] + '</span>' + rest + '</div>';
      }
      return '<div class="log-line ' + cls + '">' + l + '</div>';
    }).join('');
    if (wasAtBottom) logBox.scrollTop = logBox.scrollHeight;

    // PRs
    const prDiv = document.getElementById('prList');
    if (data.prs.length === 0) {
      prDiv.innerHTML = '<div class="no-data">No open auto-worker PRs. Agent will pick up the next issue on the next run.</div>';
    } else {
      prDiv.innerHTML = data.prs.map(p =>
        '<div class="pr-row"><span class="pr-num">#' + p.number + '</span><span class="pr-title">' + p.title + '</span><span class="pr-badge">Open</span></div>'
      ).join('');
    }

    // Issues
    const issueDiv = document.getElementById('issueList');
    if (data.issues.length === 0) {
      issueDiv.innerHTML = '<div class="no-data">No open issues.</div>';
    } else {
      issueDiv.innerHTML = data.issues.map(i => {
        const pc = priorityClass(i.labels || []);
        const labelHtml = (i.labels || []).filter(l => l.name.startsWith('P')).map(l =>
          '<span class="issue-label ' + pc + '">' + l.name + '</span>'
        ).join('');
        return '<div class="issue-row"><span class="issue-num">#' + i.number + '</span><span class="issue-title">' + i.title + '</span>' + labelHtml + '</div>';
      }).join('');
    }

  } catch(e) {
    console.error('Refresh error:', e);
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class MonitorHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/api/status":
            data = {
                "cron": get_cron_status(),
                "state": read_state(),
                "log_lines": [l.rstrip() for l in read_log(150)],
                "prs": get_open_prs(),
                "issues": get_issues(),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        else:
            self.send_error(404)


def main():
    print()
    print("  ┌─────────────────────────────────────┐")
    print("  │   DCN Auto-Worker Monitor            │")
    print("  │   http://localhost:7890               │")
    print("  │   Press Ctrl+C to quit               │")
    print("  └─────────────────────────────────────┘")
    print()

    server = HTTPServer(("127.0.0.1", PORT), MonitorHandler)
    threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down monitor.")
        server.server_close()


if __name__ == "__main__":
    main()
