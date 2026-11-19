"""Minimal load test (httpx + threads). Measures latency per endpoint under concurrency against a running API.
Usage: python scripts/loadtest.py http://localhost:18080 email password [concurrency] [requests]
Results are specific to the machine/DB it runs on; they are evidence about relative bottlenecks, not capacity claims."""
import json, statistics, sys, threading, time
import httpx

base, email, pw = sys.argv[1:4]
conc = int(sys.argv[4]) if len(sys.argv) > 4 else 8
n = int(sys.argv[5]) if len(sys.argv) > 5 else 80
tok = httpx.post(f"{base}/auth/login", json={"email": email, "password": pw}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
ENDPOINTS = [("health", "/health", False), ("patterns (taxonomy)", "/patterns", True), ("explorer p1", "/explorer?limit=30", True),
             ("explorer filtered", "/explorer?platform=codeforces&min_rating=1500&max_rating=1800&limit=30", True),
             ("patterns/coverage", "/patterns/coverage", True), ("mastery", "/mastery", True), ("daily (cached after 1st)", "/daily", True),
             ("contests", "/contests?limit=100", True), ("sheets", "/sheets", True)]
out = {}
for name, path, auth in ENDPOINTS:
    lat, errs, lock = [], 0, threading.Lock()
    per = max(1, n // conc)
    def worker():
        global errs
        with httpx.Client(base_url=base, headers=H if auth else {}, timeout=60) as c:
            for _ in range(per):
                t = time.perf_counter()
                try:
                    r = c.get(path); ok = r.status_code == 200
                except Exception:
                    ok = False
                d = (time.perf_counter() - t) * 1000
                with lock:
                    lat.append(d)
                    if not ok: errs += 1
    t0 = time.perf_counter()
    ts = [threading.Thread(target=worker) for _ in range(conc)]
    [t.start() for t in ts]; [t.join() for t in ts]
    wall = time.perf_counter() - t0
    lat.sort()
    out[name] = {"requests": len(lat), "errors": errs, "rps": round(len(lat) / wall, 1), "p50_ms": round(statistics.median(lat), 1),
                 "p95_ms": round(lat[int(.95 * len(lat)) - 1], 1), "max_ms": round(lat[-1], 1)}
print(json.dumps(out, indent=1))
