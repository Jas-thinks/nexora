"""Usage: PYTHONPATH=. CODEMIND_DATABASE_URL=sqlite:///./dev.db python scripts/run_eval.py [--synthetic N]
The synthetic part writes simulated users; it runs on a COPY of the database and never touches the source DB."""
import json, shutil, sys, tempfile
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.eval import offline
from app.models.integrations import ConnectedProfile

url = get_settings().database_url
src = url.replace("sqlite:///", "")
n = int(sys.argv[sys.argv.index("--synthetic") + 1]) if "--synthetic" in sys.argv else 0
hist = int(sys.argv[sys.argv.index("--history") + 1]) if "--history" in sys.argv else 70
S = sessionmaker(bind=create_engine(url))
report = {"real": [], "synthetic": None}
with S() as db:
    uids = sorted({u for (u,) in db.execute(select(ConnectedProfile.user_id).where(ConnectedProfile.platform == "codeforces"))})
    for u in uids:
        r = offline.real_temporal_eval(db, u)
        if r: report["real"].append(r)
if n:
    tmp = tempfile.mkdtemp() + "/scratch.db"; shutil.copy(src, tmp)
    with sessionmaker(bind=create_engine(f"sqlite:///{tmp}"))() as db:
        report["synthetic"] = offline.synthetic_eval(db, n_students=n, history=hist)
print(json.dumps(report, indent=1, default=str))
