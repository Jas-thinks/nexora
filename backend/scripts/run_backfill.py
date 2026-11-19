"""Run real backfills. Usage: PYTHONPATH=. CODEMIND_DATABASE_URL=... python scripts/run_backfill.py [platform ...] [--details-dmoj N]
Resumable: re-running continues from the saved checkpoint."""
import json, sys, time
from app.core.db import SessionLocal
from app.sources.backfill import run_backfill, run_details
from app.sources.sources import SOURCES

args = sys.argv[1:]
det = int(args[args.index("--details-dmoj") + 1]) if "--details-dmoj" in args else 0
plats = [a for a in args if a in SOURCES] or list(SOURCES)
for plat in plats:
    t = time.time()
    with SessionLocal() as db:
        src = SOURCES[plat]()
        rep = run_backfill(db, src)
        rep["seconds"] = round(time.time() - t, 1)
        print(json.dumps(rep), flush=True)
        if plat == "dmoj" and det:
            t = time.time(); d = run_details(db, src, limit=det); d["seconds"] = round(time.time() - t, 1); print(json.dumps({"details": d}), flush=True)
