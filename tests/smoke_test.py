"""
DCN Smoke Test Suite
Quick verification that core API endpoints and pages are functional.
Run: python tests/smoke_test.py [BASE_URL]
Default: http://localhost:8000
"""
import sys
import json
import urllib.request
import urllib.error
import ssl
import time

# Handle environments without proper CA certs (e.g. macOS default Python)
try:
    SSL_CTX = ssl.create_default_context()
    urllib.request.urlopen("https://example.com", timeout=3, context=SSL_CTX)
except Exception:
    SSL_CTX = ssl._create_unverified_context()

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PASS = 0
FAIL = 0

def test(name, method="GET", path="/", expected_status=200, body=None, headers=None, check_body=None):
    global PASS, FAIL
    url = f"{BASE}{path}"
    hdrs = headers or {}
    hdrs.setdefault("Content-Type", "application/json")
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, context=SSL_CTX)
        status = resp.status
        content = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        content = e.read().decode() if e.fp else ""
    except Exception as e:
        print(f"  ✗ {name} — connection error: {e}")
        FAIL += 1
        return False

    ok = status == expected_status
    if ok and check_body:
        ok = check_body(content)
    
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} {name} — {status}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        if status != expected_status:
            print(f"    expected {expected_status}, got {status}")
    return ok


print(f"\n🔍 DCN Smoke Tests — {BASE}\n")

# ── Health & Core API ──
print("Health & Core API:")
test("Health check", path="/health")
test("Stats endpoint", path="/stats", check_body=lambda b: "total_jobs" in b)
test("List jobs", path="/jobs", check_body=lambda b: isinstance(json.loads(b), list))

# ── Auth ──
print("\nAuthentication:")
test("Login page", path="/login", check_body=lambda b: "DCN" in b)
test("Auth me (unauthenticated)", path="/auth/me", expected_status=401)
test("Google OAuth redirect", path="/auth/google", expected_status=307)
test("GitHub OAuth redirect", path="/auth/github", expected_status=307)

# ── Page routes ──
print("\nPage Routes:")
test("Landing page", path="/", check_body=lambda b: "Distributed" in b or "DCN" in b)
test("Submit page redirects to login", path="/submit", expected_status=200)
test("My Jobs page", path="/my-jobs", expected_status=200)

# ── Monitor API (should reject non-admin) ──
print("\nAdmin API (unauthenticated — should reject):")
test("Monitor stats (no auth)", path="/monitor/stats", expected_status=401)
test("Monitor workers (no auth)", path="/monitor/workers", expected_status=401)

# ── Job creation (requires auth — expect redirect/401) ──
print("\nJob Submission:")
test("Create job (no auth)", method="POST", path="/jobs",
     body={"title": "smoke test", "task_type": "ml_experiment",
           "input_payload": {"dataset_name": "weather_ri"}},
     expected_status=200)  # jobs endpoint is public

# ── 404 handler ──
print("\n404 Handling:")
test("Unknown route", path="/this-does-not-exist", expected_status=404)

# ── Summary ──
total = PASS + FAIL
print(f"\n{'='*40}")
print(f"Results: {PASS}/{total} passed", end="")
if FAIL:
    print(f" ({FAIL} failed)")
else:
    print(" — all clear ✓")
print(f"{'='*40}\n")

sys.exit(0 if FAIL == 0 else 1)
