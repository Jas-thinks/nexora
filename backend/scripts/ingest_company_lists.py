"""Fetch community-reported company problem lists (see app/resources/company_lists.py for the LICENCE WARNING).
Usage: PYTHONPATH=. CODEMIND_DATABASE_URL=... python scripts/ingest_company_lists.py [--only "Amazon" "TCS" ...]"""
import json, sys
from app.core.db import SessionLocal
from app.resources import company_lists

only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None
with SessionLocal() as db:
    print(json.dumps(company_lists.run(db, only)))
