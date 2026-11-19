"""Measures the LLM pattern proposer against WEAK ground truth (patterns implied by platform tags). Tag-implied patterns are coarse, so
this checks plausibility, not correctness of fine labels (those need human review). Usage: python scripts/eval_label_llm.py N"""
import json, random, sys, time
from sqlalchemy import select
from app.core.db import SessionLocal
from app.llm.router import Router
from app.models.catalog import Problem
from app.patterns import labeling
from app.patterns.mapping import patterns_for

n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
r = Router(); rng = random.Random(5)
with SessionLocal() as db:
    pool = [p for p in db.scalars(select(Problem).where(Problem.platform == "codeforces", Problem.rating.is_not(None))) if len(patterns_for(p.tags)) >= 1]
    sample = rng.sample(pool, n); rows = []
    for p in sample:
        t = time.time(); props = labeling.llm_proposals(r, p); truth = set(patterns_for(p.tags)); pred = {x[0] for x in props}
        rows.append({"name": p.name, "tags": p.tags, "truth": sorted(truth), "pred": sorted(pred), "hit": bool(pred & truth), "any": bool(pred), "s": round(time.time() - t, 1)})
        print(json.dumps(rows[-1]), flush=True)
    got = sum(x["any"] for x in rows); hit = sum(x["hit"] for x in rows)
    print(json.dumps({"n": n, "model": r.status()["configured"], "proposed_anything": got, "agrees_with_tag_derived_pattern": hit, "agreement_rate_of_those_with_proposals": round(hit / got, 3) if got else None}))
