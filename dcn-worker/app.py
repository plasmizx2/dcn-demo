#!/usr/bin/env python3
"""
DCN Worker — Desktop GUI App (Web-based)
Double-click to run. Opens in your browser.
"""

import os
import sys
import json
import time
import socket
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Ensure we can import sibling modules
sys.path.insert(0, os.path.dirname(__file__))

import hardware
import requests as req

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, ".worker_state.json")
GUI_PORT = 7777

# --- Shared State ---
state = {
    "status": "offline",       # offline, connecting, setting_up, idle, working, disconnected, error
    "current_task": None,
    "tasks_completed": 0,
    "total_earnings": 0.0,
    "logs": [],
    "worker_id": None,
    "running": False,
}
state_lock = threading.Lock()


def add_log(msg, tag="info"):
    with state_lock:
        ts = datetime.now().strftime("%H:%M:%S")
        state["logs"].append({"time": ts, "msg": msg, "tag": tag})
        # Keep last 200
        if len(state["logs"]) > 200:
            state["logs"] = state["logs"][-200:]


def set_status(s):
    with state_lock:
        state["status"] = s


# ═══════════════════════════════════════════
# Worker Engine (background thread)
# ═══════════════════════════════════════════

class WorkerEngine:
    def __init__(self):
        self.server_url = ""
        self.worker_id = None
        self.worker_name = ""
        self.task_types = []
        self.thread = None
        self._audio_handler = None
        self._sentiment_handler = None

    def start(self, server_url, worker_name, task_types):
        self.server_url = server_url.rstrip("/")
        self.worker_name = worker_name
        self.task_types = task_types
        with state_lock:
            state["running"] = True
            state["tasks_completed"] = 0
            state["total_earnings"] = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def stop(self):
        with state_lock:
            state["running"] = False

    def _heartbeat_loop(self):
        """Send heartbeat every 15s independently of task processing."""
        while state["running"]:
            if self.worker_id:
                self._heartbeat()
            time.sleep(15)

    def _register(self, hw_info):
        add_log("Registering with server...")
        try:
            resp = req.post(
                f"{self.server_url}/workers/register",
                json={"node_name": self.worker_name, "capabilities": {
                    "tier": hw_info["tier"], "ram_gb": hw_info["ram_gb"],
                    "cores": hw_info["cores"], "has_gpu": hw_info["has_gpu"],
                    "gpu_type": hw_info["gpu_type"], "task_types": self.task_types,
                }}, timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.worker_id = data["id"]
                with open(STATE_FILE, "w") as f:
                    json.dump({"worker_id": self.worker_id, "worker_name": self.worker_name}, f)
                with state_lock:
                    state["worker_id"] = self.worker_id
                add_log(f"Registered! ID: {self.worker_id[:8]}...", "success")
                return True
            else:
                add_log(f"Registration failed: {resp.text}", "error")
                return False
        except Exception as e:
            add_log(f"Can't reach server: {e}", "error")
            return False

    def _heartbeat(self):
        try:
            resp = req.post(f"{self.server_url}/workers/heartbeat",
                            json={"worker_node_id": self.worker_id}, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _claim(self):
        try:
            hw = hardware.detect()
            resp = req.post(f"{self.server_url}/tasks/claim",
                            json={"worker_node_id": self.worker_id, "task_types": self.task_types, "worker_tier": hw["tier"]}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _fetch_job(self, job_id):
        try:
            resp = req.get(f"{self.server_url}/jobs/{job_id}", timeout=10)
            if resp.status_code == 200:
                job = resp.json()
                if isinstance(job.get("input_payload"), str):
                    try: job["input_payload"] = json.loads(job["input_payload"])
                    except: job["input_payload"] = {}
                return job
        except Exception:
            pass
        return None

    def _complete(self, task_id, result_text, exec_time):
        try:
            resp = req.post(f"{self.server_url}/tasks/{task_id}/complete",
                            json={"result_text": result_text, "execution_time_seconds": exec_time}, timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _fail(self, task_id):
        try: req.post(f"{self.server_url}/tasks/{task_id}/fail", timeout=10)
        except: pass

    def _get_handler(self, task_type):
        from handlers import image_processing, web_scraping
        if task_type == "image_processing": return image_processing.handle
        if task_type == "web_scraping": return web_scraping.handle
        if task_type == "audio_transcription":
            if not self._audio_handler:
                from handlers import audio_transcription
                self._audio_handler = audio_transcription.handle
            return self._audio_handler
        if task_type == "sentiment_classification":
            if not self._sentiment_handler:
                from handlers import sentiment_classification
                self._sentiment_handler = sentiment_classification.handle
            return self._sentiment_handler
        if task_type == "ml_experiment":
            from handlers import ml_experiment
            return ml_experiment.handle
        return None

    # Earnings per second of execution time, by task type and tier
    TASK_RATES = {
        "ml_experiment":          0.0120,
        "audio_transcription":    0.0090,
        "image_processing":       0.0060,
        "web_scraping":           0.0035,
        "sentiment_classification": 0.0025,
    }
    TIER_MULT = {1: 1.0, 2: 1.6, 3: 2.5}

    def _compute_earnings(self, task_type, exec_time, tier):
        rate = self.TASK_RATES.get(task_type, 0.005)
        mult = self.TIER_MULT.get(tier, 1.0)
        return round(exec_time * rate * mult, 4)

    def _loop(self):
        hw = hardware.detect()
        set_status("connecting")

        # Check saved state
        saved = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)

        self.worker_id = saved.get("worker_id")
        saved_name = saved.get("worker_name", "")
        with state_lock:
            state["worker_id"] = self.worker_id

        # Re-register if name changed
        if saved_name and saved_name != self.worker_name:
            add_log(f"Name changed ({saved_name} -> {self.worker_name}), re-registering...", "warn")
            self.worker_id = None
        elif self.worker_id:
            add_log(f"Found saved ID: {self.worker_id[:8]}...")
            if not self._heartbeat():
                add_log("Saved ID invalid, re-registering...", "warn")
                self.worker_id = None

        if not self.worker_id:
            if not self._register(hw):
                set_status("error")
                return

        # Dependencies
        add_log("Checking dependencies...")
        set_status("setting_up")
        try:
            import installer
            installer.setup_dependencies(hw["tier"])
            add_log("Dependencies ready.", "success")
        except Exception as e:
            add_log(f"Dependency warning: {e}", "warn")

        add_log(f"Listening for: {', '.join(self.task_types)}")
        set_status("idle")

        while state["running"]:
            if not self._heartbeat():
                add_log("Server unreachable, retrying...", "warn")
                set_status("disconnected")
                time.sleep(10)
                continue

            result = self._claim()

            if result and result.get("claimed"):
                task = result["task"]
                task_id = task["id"]
                task_name = task.get("task_name", "unknown")
                job_id = task.get("job_id")

                set_status("working")
                with state_lock:
                    state["current_task"] = task_name
                add_log(f"Claimed: {task_name}", "task")

                job = self._fetch_job(job_id)
                if not job:
                    add_log(f"Could not fetch job {job_id[:8]}", "error")
                    self._fail(task_id)
                    set_status("idle")
                    with state_lock: state["current_task"] = None
                    continue

                task_type = job.get("task_type", "")
                handler = self._get_handler(task_type)
                if not handler:
                    add_log(f"No handler for: {task_type}", "error")
                    self._fail(task_id)
                    set_status("idle")
                    with state_lock: state["current_task"] = None
                    continue

                if isinstance(task.get("task_payload"), str):
                    try: task["task_payload"] = json.loads(task["task_payload"])
                    except: task["task_payload"] = {}

                add_log(f"Processing: {task_type}...")
                start_time = time.time()

                try:
                    result_text = handler(task, job)
                    exec_time = round(time.time() - start_time, 2)
                    add_log(f"Done! {len(result_text)} chars in {exec_time}s", "success")

                    comp = self._complete(task_id, result_text, exec_time)
                    if comp and comp.get("completed"):
                        earned = self._compute_earnings(task_type, exec_time, hw["tier"])
                        with state_lock:
                            state["tasks_completed"] += 1
                            state["total_earnings"] += earned
                        add_log(f"Earned ${earned:.4f} for {task_type} ({exec_time}s, Tier {hw['tier']})", "success")
                        if comp.get("job_aggregated"):
                            add_log(f"Job {job_id[:8]} fully completed!", "success")
                except Exception as e:
                    add_log(f"Task failed: {e}", "error")
                    self._fail(task_id)

                with state_lock: state["current_task"] = None
                set_status("idle")
            else:
                set_status("idle")
                for _ in range(10):
                    if not state["running"]:
                        break
                    time.sleep(0.5)

        set_status("offline")
        add_log("Worker stopped.")


engine = WorkerEngine()


# ═══════════════════════════════════════════
# HTTP Server (serves the GUI + API)
# ═══════════════════════════════════════════

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DCN Worker Node</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{--bg:#14161e;--surface:rgba(255,255,255,0.08);--border:rgba(255,255,255,0.12);--border2:rgba(255,255,255,0.14);--text:#e8e8ec;--muted:#b4b4bc;--dim:#8a8a96;--dark:#52525b;--accent:#7c3aed;--accent2:#6366f1;--accent3:#3b82f6;--green:#22c55e;--red:#ef4444;--yellow:#eab308}
  html,body{height:100%}
  body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;overflow:hidden}

  /* LAYOUT */
  .page{display:grid;grid-template-rows:auto 1fr;height:100vh}

  /* NAV */
  .topnav{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 28px}
  .topnav-left{display:flex;align-items:center;gap:12px}
  .topnav-logo{font-weight:800;font-size:1rem;color:#fff;letter-spacing:-0.5px}
  .topnav-logo span{background:linear-gradient(135deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .topnav-sep{color:var(--dark);font-size:0.8rem}
  .topnav-page{font-size:0.82rem;color:var(--muted);font-weight:500}
  .status-pill{display:flex;align-items:center;gap:8px;padding:6px 16px;border-radius:20px;border:1px solid var(--border);background:var(--surface);font-size:0.78rem;font-weight:600}
  .status-dot{width:8px;height:8px;border-radius:50%;background:var(--dark);flex-shrink:0}
  .status-dot.online{background:var(--green);box-shadow:0 0 8px rgba(34,197,94,0.4);animation:pulse 2s infinite}
  .status-dot.working{background:var(--accent2);box-shadow:0 0 8px rgba(99,102,241,0.4);animation:pulse 1s infinite}
  .status-dot.warn{background:var(--yellow);box-shadow:0 0 8px rgba(234,179,8,0.3)}
  .status-dot.error{background:var(--red);box-shadow:0 0 8px rgba(239,68,68,0.3)}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

  /* MAIN GRID */
  .main{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto 1fr;gap:16px;padding:20px 28px;overflow:hidden}

  /* CARDS */
  .card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 24px;transition:border-color 0.2s}
  .card:hover{border-color:var(--border2)}
  .card-label{font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin-bottom:14px}

  /* STATS ROW - full width */
  .stats-row{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 24px;position:relative;overflow:hidden}
  .stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:14px 14px 0 0}
  .stat-card.purple::before{background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .stat-card.green::before{background:var(--green)}
  .stat-card.blue::before{background:var(--accent3)}
  .stat-card.yellow::before{background:var(--yellow)}
  .stat-val{font-size:2rem;font-weight:800;letter-spacing:-1px;color:#fff}
  .stat-val.accent{background:linear-gradient(135deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .stat-val.green{color:var(--green)}
  .stat-val.blue{color:var(--accent3)}
  .stat-lbl{font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;color:var(--dim);margin-top:4px}
  .stat-sub{font-size:0.72rem;color:var(--muted);margin-top:8px;min-height:18px}

  /* HARDWARE CARD */
  .hw-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}
  .hw-item{text-align:center;padding:14px 8px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:10px}
  .hw-label{font-size:0.62rem;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;color:var(--dim);margin-bottom:6px}
  .hw-value{font-size:1.05rem;font-weight:700;color:#fff}
  .hw-value.tier{background:linear-gradient(135deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:1.2rem}
  .hw-types{font-size:0.72rem;color:var(--dim);line-height:1.5}
  .hw-types span{display:inline-block;padding:3px 10px;border-radius:20px;background:rgba(255,255,255,0.04);border:1px solid var(--border);margin:2px 3px;font-size:0.65rem;color:var(--muted);font-weight:500}

  /* CONNECTION CARD */
  .field{margin-bottom:14px}
  .field:last-child{margin-bottom:0}
  .field label{display:block;font-size:0.68rem;font-weight:600;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
  .field input{width:100%;padding:11px 14px;background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:0.85rem;font-family:inherit;transition:all 0.2s}
  .field input:focus{outline:none;border-color:rgba(124,58,237,0.5);box-shadow:0 0 0 3px rgba(124,58,237,0.1)}
  .field input:disabled{opacity:0.4;cursor:not-allowed}

  /* BUTTON */
  .btn-start{width:100%;padding:14px;border:none;border-radius:12px;font-size:0.95rem;font-weight:700;cursor:pointer;transition:all 0.2s;font-family:inherit;background:linear-gradient(135deg,var(--accent),var(--accent3));color:#fff;margin-top:16px}
  .btn-start:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(124,58,237,0.35)}
  .btn-start.stop{background:linear-gradient(135deg,#dc2626,var(--red))}
  .btn-start.stop:hover{box-shadow:0 6px 24px rgba(239,68,68,0.35)}

  /* LOG - full width bottom */
  .log-panel{grid-column:1/-1;display:flex;flex-direction:column;min-height:0}
  .log-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
  .log-box{flex:1;background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:12px;padding:16px;overflow-y:auto;font-family:'SF Mono','Fira Code','Menlo',monospace;font-size:0.75rem;line-height:1.7;min-height:0}
  .log-box::-webkit-scrollbar{width:5px}
  .log-box::-webkit-scrollbar-track{background:transparent}
  .log-box::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.10);border-radius:3px}
  .log-line{padding:1px 0}
  .log-line .ts{color:#3f3f46;margin-right:6px}
  .log-line.info{color:var(--text)}
  .log-line.success{color:var(--green)}
  .log-line.error{color:var(--red)}
  .log-line.warn{color:var(--yellow)}
  .log-line.task{color:var(--accent3)}

  /* RESPONSIVE */
  @media(max-width:900px){
    .main{grid-template-columns:1fr}
    .stats-row{grid-template-columns:repeat(2,1fr)}
  }
</style>
</head>
<body>
<div class="page">
  <!-- NAV -->
  <div class="topnav">
    <div class="topnav-left">
      <div class="topnav-logo"><span>DCN</span> Worker</div>
    </div>
    <div class="status-pill">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">Offline</span>
    </div>
  </div>

  <!-- MAIN -->
  <div class="main">
    <!-- STATS ROW -->
    <div class="stats-row">
      <div class="stat-card purple">
        <div class="stat-val accent" id="taskCount">0</div>
        <div class="stat-lbl">Tasks Completed</div>
        <div class="stat-sub" id="currentTask"></div>
      </div>
      <div class="stat-card green">
        <div class="stat-val green" id="earnings">$0.00</div>
        <div class="stat-lbl">Total Earned</div>
        <div class="stat-sub" id="earningRate"></div>
      </div>
      <div class="stat-card blue">
        <div class="stat-val blue" id="uptimeVal">--</div>
        <div class="stat-lbl">Uptime</div>
        <div class="stat-sub" id="workerIdDisplay"></div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-val" id="tierVal" style="color:var(--yellow)">--</div>
        <div class="stat-lbl">Worker Tier</div>
        <div class="stat-sub" id="hwSummary"></div>
      </div>
    </div>

    <!-- HARDWARE -->
    <div class="card">
      <div class="card-label">Hardware Detection</div>
      <div class="hw-grid" id="hwGrid"></div>
      <div class="hw-types" id="hwTypes"></div>
    </div>

    <!-- CONNECTION -->
    <div class="card">
      <div class="card-label">Connection</div>
      <div class="field">
        <label>Server URL</label>
        <input type="text" id="serverUrl" placeholder="http://localhost:8000">
      </div>
      <div class="field">
        <label>Worker Name</label>
        <input type="text" id="workerName" placeholder="my-laptop">
      </div>
      <button class="btn-start" id="startBtn" onclick="toggleWorker()">Start Worker</button>
    </div>

    <!-- LOG -->
    <div class="log-panel card" style="padding-bottom:16px">
      <div class="card-label" style="margin-bottom:10px">Activity Log</div>
      <div class="log-box" id="logBox">
        <div class="log-line info"><span class="ts">[--:--:--]</span> Ready. Click Start to join the network.</div>
      </div>
    </div>
  </div>
</div>

<script>
  let isRunning = false;
  let lastLogCount = 0;
  let startTime = null;

  async function init() {
    const hw = await (await fetch('/api/hardware')).json();
    document.getElementById('hwGrid').innerHTML = [
      {l:'CPU', v:hw.cores+' cores'}, {l:'RAM', v:hw.ram_gb+' GB'},
      {l:'GPU', v:hw.gpu_type||'None'}, {l:'Tier', v:'Tier '+hw.tier},
    ].map(x => `<div class="hw-item"><div class="hw-label">${x.l}</div><div class="hw-value${x.l==='Tier'?' tier':''}">${x.v}</div></div>`).join('');

    document.getElementById('hwTypes').innerHTML = hw.supported_task_types.map(t=>`<span>${t.replace(/_/g,' ')}</span>`).join('');
    document.getElementById('tierVal').textContent = 'T' + hw.tier;
    document.getElementById('hwSummary').textContent = hw.cores + ' cores / ' + hw.ram_gb + ' GB';

    const cfg = await (await fetch('/api/config')).json();
    document.getElementById('serverUrl').value = cfg.server_url || 'http://localhost:8000';
    document.getElementById('workerName').value = cfg.worker_name || '';

    setInterval(pollState, 1000);
    setInterval(updateUptime, 1000);
  }

  function updateUptime() {
    if (!startTime || !isRunning) { document.getElementById('uptimeVal').textContent = '--'; return; }
    const s = Math.floor((Date.now() - startTime) / 1000);
    const h = Math.floor(s/3600); const m = Math.floor((s%3600)/60); const sec = s%60;
    document.getElementById('uptimeVal').textContent = (h>0?h+'h ':'') + m + 'm ' + sec + 's';
  }

  async function toggleWorker() {
    if (!isRunning) {
      const url = document.getElementById('serverUrl').value.trim();
      const name = document.getElementById('workerName').value.trim();
      if (!url || !name) { alert('Fill in server URL and worker name'); return; }
      startTime = Date.now();
      await fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({server_url: url, worker_name: name})
      });
    } else {
      startTime = null;
      await fetch('/api/stop', {method:'POST'});
    }
  }

  const STATUS_MAP = {
    offline:      {dot:'', text:'Offline'},
    connecting:   {dot:'warn', text:'Connecting...'},
    setting_up:   {dot:'warn', text:'Setting Up...'},
    idle:         {dot:'online', text:'Online - Waiting'},
    working:      {dot:'working', text:'Processing'},
    disconnected: {dot:'error', text:'Disconnected'},
    error:        {dot:'error', text:'Error'},
  };

  async function pollState() {
    try {
      const s = await (await fetch('/api/state')).json();
      const sm = STATUS_MAP[s.status] || STATUS_MAP.offline;

      document.getElementById('statusDot').className = 'status-dot ' + sm.dot;
      document.getElementById('statusText').textContent = sm.text;
      document.getElementById('taskCount').textContent = s.tasks_completed;
      document.getElementById('earnings').textContent = '$' + s.total_earnings.toFixed(2);
      document.getElementById('currentTask').textContent = s.current_task ? 'Working on: ' + s.current_task : (s.running ? 'Waiting for tasks...' : '');
      document.getElementById('workerIdDisplay').textContent = s.worker_id ? 'ID: ' + s.worker_id.substring(0,8) + '...' : '';

      if (s.tasks_completed > 0 && startTime) {
        const mins = (Date.now() - startTime) / 60000;
        const rate = (s.total_earnings / mins).toFixed(3);
        document.getElementById('earningRate').textContent = '$' + rate + '/min';
      }

      isRunning = s.running;
      const btn = document.getElementById('startBtn');
      const urlInput = document.getElementById('serverUrl');
      const nameInput = document.getElementById('workerName');
      if (isRunning) {
        btn.textContent = 'Stop Worker';
        btn.className = 'btn-start stop';
        urlInput.disabled = true;
        nameInput.disabled = true;
        if (!startTime) startTime = Date.now();
      } else {
        btn.textContent = 'Start Worker';
        btn.className = 'btn-start';
        urlInput.disabled = false;
        nameInput.disabled = false;
      }

      if (s.logs.length !== lastLogCount) {
        const box = document.getElementById('logBox');
        const wasAtBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 30;
        box.innerHTML = s.logs.map(l =>
          `<div class="log-line ${l.tag}"><span class="ts">[${l.time}]</span> ${l.msg}</div>`
        ).join('');
        if (wasAtBottom) box.scrollTop = box.scrollHeight;
        lastLogCount = s.logs.length;
      }
    } catch(e) {}
  }

  init();
</script>
</body>
</html>"""


class GUIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        if self.path == "/":
            self._html(HTML_PAGE)
        elif self.path == "/api/state":
            with state_lock:
                self._json({
                    "status": state["status"],
                    "current_task": state["current_task"],
                    "tasks_completed": state["tasks_completed"],
                    "total_earnings": state["total_earnings"],
                    "logs": state["logs"],
                    "running": state["running"],
                    "worker_id": state["worker_id"],
                })
        elif self.path == "/api/hardware":
            hw = hardware.detect()
            self._json(hw)
        elif self.path == "/api/config":
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {"server_url": "http://localhost:8000", "worker_name": ""}
            if not cfg.get("worker_name"):
                cfg["worker_name"] = f"{socket.gethostname()}-worker"
            self._json(cfg)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/start":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            server_url = body.get("server_url", "http://localhost:8000")
            worker_name = body.get("worker_name", f"{socket.gethostname()}-worker")

            # Save config
            with open(CONFIG_FILE, "w") as f:
                json.dump({"server_url": server_url, "worker_name": worker_name}, f, indent=2)

            hw = hardware.detect()
            engine.start(server_url, worker_name, hw["supported_task_types"])
            self._json({"started": True})

        elif self.path == "/api/stop":
            engine.stop()
            self._json({"stopped": True})

        else:
            self.send_error(404)


def main():
    print()
    print("  ██████╗  ██████╗███╗   ██╗")
    print("  ██╔══██╗██╔════╝████╗  ██║")
    print("  ██║  ██║██║     ██╔██╗ ██║")
    print("  ██║  ██║██║     ██║╚██╗██║")
    print("  ██████╔╝╚██████╗██║ ╚████║")
    print("  ╚═════╝  ╚═════╝╚═╝  ╚═══╝")
    print("  Worker App")
    print()

    server = HTTPServer(("127.0.0.1", GUI_PORT), GUIHandler)
    url = f"http://localhost:{GUI_PORT}"
    print(f"  Open in browser: {url}")
    print(f"  Press Ctrl+C to quit\n")

    # Auto-open browser
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        engine.stop()
        server.server_close()


if __name__ == "__main__":
    main()
