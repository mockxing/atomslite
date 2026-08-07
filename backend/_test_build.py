"""Trigger a real build on Railway to test LLM connectivity."""
import urllib.request, json, time

BASE = "https://atoms-lite-backend-production.up.railway.app"

data = json.dumps({"title": "todo app test"}).encode()
req = urllib.request.Request(
    f"{BASE}/api/projects",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
r = urllib.request.urlopen(req, timeout=15)
proj = json.loads(r.read().decode())
pid = proj["id"]
print(f"Project created: {pid}")

req2 = urllib.request.Request(
    f"{BASE}/api/build/stream",
    data=json.dumps({"project_id": pid, "prompt": "todo app"}).encode(),
    headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    method="POST",
)
try:
    r2 = urllib.request.urlopen(req2, timeout=120)
    start = time.time()
    while time.time() - start < 90:
        line = r2.readline()
        if not line:
            break
        decoded = line.decode("utf-8", "replace").strip()
        if not decoded:
            continue
        if "failed" in decoded.lower() or "error" in decoded.lower() or "LLM provider" in decoded:
            print(f"[FAIL] {decoded[:200]}")
            break
        if "analysis" in decoded.lower() and "running" in decoded.lower():
            print(f"[STEP] {decoded[:150]}")
        elif "completed" in decoded.lower() or "ready" in decoded.lower() or "artifact" in decoded.lower():
            print(f"[OK] {decoded[:200]}")
            break
    print(f"Stream ended after {time.time()-start:.0f}s")
except Exception as e:
    print(f"Stream error: {type(e).__name__}: {e}")

time.sleep(3)
req3 = urllib.request.Request(f"{BASE}/api/projects/{pid}")
r3 = urllib.request.urlopen(req3, timeout=15)
proj_status = json.loads(r3.read().decode())
print(f"Project status: {proj_status.get('status')}")
