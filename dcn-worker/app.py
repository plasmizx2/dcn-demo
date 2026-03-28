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

    def stop(self):
        with state_lock:
            state["running"] = False

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
            resp = req.post(f"{self.server_url}/tasks/claim",
                            json={"worker_node_id": self.worker_id, "task_types": self.task_types}, timeout=10)
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
        return None

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
                        reward = job.get("reward_amount", 0) or 0
                        with state_lock:
                            state["tasks_completed"] += 1
                            state["total_earnings"] += reward / 3
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
<title>DCN Worker</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0a0a0f; color: #e0e0e0; min-height: 100vh;
  }
  .container { max-width: 540px; margin: 0 auto; padding: 28px 20px; }

  /* Header */
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
  .header h1 { font-size: 1.6rem; font-weight: 700; color: #fff; }
  .header h1 span { color: #6c63ff; }
  .status-badge {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 14px; border-radius: 20px;
    background: rgba(102,99,255,0.08); border: 1px solid #1e1e30;
    font-size: 0.8rem; font-weight: 500;
  }
  .status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #666; flex-shrink: 0;
  }
  .status-dot.online { background: #4ade80; animation: pulse 2s infinite; }
  .status-dot.working { background: #6c63ff; animation: pulse 1s infinite; }
  .status-dot.warn { background: #fbbf24; }
  .status-dot.error { background: #ef4444; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

  /* Cards */
  .card {
    background: #141420; border: 1px solid #1e1e30;
    border-radius: 10px; padding: 18px; margin-bottom: 14px;
  }
  .card-title { font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600; }

  /* Hardware grid */
  .hw-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
  .hw-item { text-align: center; }
  .hw-label { font-size: 0.7rem; color: #666; }
  .hw-value { font-size: 1rem; font-weight: 700; color: #e0e0e0; }
  .hw-value.tier { color: #6c63ff; }
  .hw-types { font-size: 0.75rem; color: #555; }

  /* Config inputs */
  .field { margin-bottom: 12px; }
  .field label { display: block; font-size: 0.75rem; color: #666; margin-bottom: 4px; font-weight: 500; }
  .field input {
    width: 100%; padding: 10px 12px; background: #0d0d15; border: 1px solid #2a2a40;
    border-radius: 8px; color: #e0e0e0; font-size: 0.9rem; font-family: inherit;
    transition: border-color 0.2s;
  }
  .field input:focus { outline: none; border-color: #6c63ff; }
  .field input:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Button */
  .btn-start {
    width: 100%; padding: 14px; border: none; border-radius: 10px;
    font-size: 1rem; font-weight: 700; cursor: pointer; transition: all 0.2s;
    background: #6c63ff; color: #fff;
  }
  .btn-start:hover { background: #5a52e0; transform: translateY(-1px); }
  .btn-start.stop { background: #ef4444; }
  .btn-start.stop:hover { background: #dc2626; }

  /* Stats row */
  .stats-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .stat { text-align: center; flex: 1; }
  .stat-value { font-size: 1.4rem; font-weight: 700; }
  .stat-label { font-size: 0.7rem; color: #666; }
  .stat-value.earnings { color: #4ade80; }
  .stat-value.tasks { color: #6c63ff; }

  .current-task {
    font-size: 0.8rem; color: #6c63ff; margin-bottom: 8px;
    min-height: 18px;
  }

  /* Log */
  .log-box {
    background: #0d0d15; border-radius: 8px; padding: 12px;
    max-height: 260px; overflow-y: auto; font-family: 'Menlo', 'Consolas', monospace;
    font-size: 0.78rem; line-height: 1.6;
  }
  .log-box::-webkit-scrollbar { width: 6px; }
  .log-box::-webkit-scrollbar-track { background: transparent; }
  .log-box::-webkit-scrollbar-thumb { background: #2a2a40; border-radius: 3px; }
  .log-line .ts { color: #444; }
  .log-line.info { color: #e0e0e0; }
  .log-line.success { color: #4ade80; }
  .log-line.error { color: #ef4444; }
  .log-line.warn { color: #fbbf24; }
  .log-line.task { color: #60a5fa; }
</style>
</head>
<body>
<div class="container">
  <!-- Header -->
  <div class="header">
    <h1><span>DCN</span> Worker</h1>
    <div class="status-badge">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">Offline</span>
    </div>
  </div>

  <!-- Hardware -->
  <div class="card">
    <div class="card-title">Hardware</div>
    <div class="hw-grid" id="hwGrid"></div>
    <div class="hw-types" id="hwTypes"></div>
  </div>

  <!-- Config -->
  <div class="card" id="configCard">
    <div class="card-title">Connection</div>
    <div class="field">
      <label>Server URL</label>
      <input type="text" id="serverUrl" placeholder="http://localhost:8000">
    </div>
    <div class="field" style="margin-bottom:0">
      <label>Worker Name</label>
      <input type="text" id="workerName" placeholder="my-laptop">
    </div>
  </div>

  <!-- Start/Stop -->
  <button class="btn-start" id="startBtn" onclick="toggleWorker()">Start Worker</button>

  <!-- Stats -->
  <div style="margin-top:14px">
    <div class="current-task" id="currentTask"></div>
    <div class="stats-row">
      <div class="stat"><div class="stat-value tasks" id="taskCount">0</div><div class="stat-label">Tasks Done</div></div>
      <div class="stat"><div class="stat-value earnings" id="earnings">$0.00</div><div class="stat-label">Earned</div></div>
    </div>
  </div>

  <!-- Log -->
  <div class="card">
    <div class="card-title">Activity Log</div>
    <div class="log-box" id="logBox">
      <div class="log-line info"><span class="ts">[--:--:--]</span> Ready. Click Start to join the network.</div>
    </div>
  </div>
</div>

<script>
  let isRunning = false;
  let lastLogCount = 0;

  // Load hardware + config on page load
  async function init() {
    const hw = await (await fetch('/api/hardware')).json();
    document.getElementById('hwGrid').innerHTML = [
      {l:'CPU', v:hw.cores+' cores'}, {l:'RAM', v:hw.ram_gb+' GB'},
      {l:'GPU', v:hw.gpu_type||'None'}, {l:'Tier', v:'Tier '+hw.tier},
    ].map(x => `<div class="hw-item"><div class="hw-label">${x.l}</div><div class="hw-value${x.l==='Tier'?' tier':''}">${x.v}</div></div>`).join('');
    document.getElementById('hwTypes').textContent = 'Supports: ' + hw.supported_task_types.map(t=>t.replace(/_/g,' ')).join(', ');

    const cfg = await (await fetch('/api/config')).json();
    document.getElementById('serverUrl').value = cfg.server_url || 'http://localhost:8000';
    document.getElementById('workerName').value = cfg.worker_name || '';

    // Start polling
    setInterval(pollState, 1000);
  }

  async function toggleWorker() {
    if (!isRunning) {
      const url = document.getElementById('serverUrl').value.trim();
      const name = document.getElementById('workerName').value.trim();
      if (!url || !name) { alert('Fill in server URL and worker name'); return; }
      await fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({server_url: url, worker_name: name})
      });
    } else {
      await fetch('/api/stop', {method:'POST'});
    }
  }

  const STATUS_MAP = {
    offline:      {dot:'', text:'Offline'},
    connecting:   {dot:'warn', text:'Connecting...'},
    setting_up:   {dot:'warn', text:'Setting Up...'},
    idle:         {dot:'online', text:'Online — Waiting'},
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
      document.getElementById('currentTask').textContent = s.current_task ? 'Working on: ' + s.current_task : '';

      // Update button
      isRunning = s.running;
      const btn = document.getElementById('startBtn');
      const urlInput = document.getElementById('serverUrl');
      const nameInput = document.getElementById('workerName');
      if (isRunning) {
        btn.textContent = 'Stop Worker';
        btn.className = 'btn-start stop';
        urlInput.disabled = true;
        nameInput.disabled = true;
      } else {
        btn.textContent = 'Start Worker';
        btn.className = 'btn-start';
        urlInput.disabled = false;
        nameInput.disabled = false;
      }

      // Update logs (only if new)
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
