"""Ingest community-reported company->problem lists from the public GitHub repo liquidslr/leetcode-company-wise-problems.

LICENCE WARNING: that repository declares no licence (all rights reserved by default). We therefore (1) never commit its files, (2) fetch at run
time on an admin's explicit command, (3) store only facts (company, problem URL/title/difficulty/topics, reported frequency, recency) and
attribute the source in the UI. Whether this is acceptable for a public product is the owner's call; remove the source by deleting rows with
Company.source == SOURCE. The data is candidate-reported and unofficial."""
import csv
import io
import time
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.resources import Company, CompanyProblem
from app.models.user import utcnow
from app.resources.tiers import DOMAINS, display_name, slugify, tier_of
from app.services.canonical import canonicalize

REPO = "liquidslr/leetcode-company-wise-problems"
SOURCE = f"github:{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
ALL_FILE, RECENT_FILE = "5. All.csv", "3. Six Months.csv"
DIFF = {"EASY": "Easy", "MEDIUM": "Medium", "HARD": "Hard"}


def parse_csv(text: str) -> list[dict]:
    """-> [{slug,url,name,difficulty,frequency,topics}] ; rows without a recognisable LeetCode URL are dropped (counted by the caller)."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        c = canonicalize((r.get("Link") or "").strip())
        if not c or c[0] != "leetcode" or not (r.get("Title") or "").strip():
            continue
        try:
            freq = max(0.0, min(100.0, float(r.get("Frequency") or 0)))
        except ValueError:
            freq = 0.0
        out.append({"slug": c[1], "url": c[2], "name": r["Title"].strip()[:300], "difficulty": DIFF.get((r.get("Difficulty") or "").strip().upper()),
                    "frequency": freq, "topics": [t.strip() for t in (r.get("Topics") or "").split(",") if t.strip()][:12]})
    return out


def _get(client: httpx.Client, url: str, retries: int = 3) -> str | None:
    for i in range(retries):
        try:
            r = client.get(url)
            if r.status_code == 404:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After", 2 * (i + 1)))); continue
            r.raise_for_status()
            return r.text
        except httpx.TransportError:
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"giving up on {url}")


def list_companies(client: httpx.Client) -> list[str]:
    r = client.get(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1")
    r.raise_for_status()
    return sorted({x["path"].split("/")[0] for x in r.json()["tree"] if x["path"].endswith(ALL_FILE)})


def store_company(db: Session, name: str, all_rows: list[dict], recent_slugs: set[str]) -> dict:
    """Idempotent: replaces this company's rows. Creates missing LeetCode problems (metadata only; the statement is never stored)."""
    slug = slugify(name)
    co = db.scalar(select(Company).where(Company.slug == slug))
    if co is None:
        co = Company(slug=slug, name=display_name(name), tier=tier_of(name), domain=DOMAINS.get(name.lower())); db.add(co); db.flush()
    else:
        co.name, co.tier, co.domain = display_name(name), tier_of(name), DOMAINS.get(name.lower())  # editorial fields follow our latest mapping
    existing = {p.external_id: p for p in db.scalars(select(Problem).where(Problem.platform == "leetcode", Problem.external_id.in_([r["slug"] for r in all_rows])))} if all_rows else {}
    added = 0
    for r in all_rows:
        p = existing.get(r["slug"])
        if p is None:
            p = Problem(platform="leetcode", external_id=r["slug"], name=r["name"], url=r["url"], canonical_url=r["url"], source_difficulty=r["difficulty"], tags=r["topics"],
                        source=SOURCE, observed_at=utcnow(), statement_access="link_only")
            db.add(p); existing[r["slug"]] = p; added += 1
        else:
            if not p.source_difficulty and r["difficulty"]:
                p.source_difficulty = r["difficulty"]
            if not p.tags and r["topics"]:
                p.tags = r["topics"]
    db.flush()
    db.execute(delete(CompanyProblem).where(CompanyProblem.company_id == co.id))
    seen = set()
    for r in all_rows:
        if r["slug"] in seen:
            continue
        seen.add(r["slug"])
        db.add(CompanyProblem(company_id=co.id, problem_id=existing[r["slug"]].id, frequency=r["frequency"], recent=r["slug"] in recent_slugs))
    co.problem_count, co.source, co.updated_at = len(seen), SOURCE, utcnow()
    db.commit()
    return {"company": name, "problems": len(seen), "new_problems": added}


def run(db: Session, only: list[str] | None = None, delay: float = 0.15, client: httpx.Client | None = None, log=print) -> dict:
    client = client or httpx.Client(timeout=30, headers={"User-Agent": "nexora-resource-ingest/1.0"}, follow_redirects=True)
    names = list_companies(client)
    if only:
        names = [n for n in names if n.lower() in {o.lower() for o in only}]
    done = failed = new = rows = 0
    for n in names:
        try:
            all_txt = _get(client, f"{RAW}/{quote(n)}/{quote(ALL_FILE)}")
            if all_txt is None:
                continue
            time.sleep(delay)
            rec_txt = _get(client, f"{RAW}/{quote(n)}/{quote(RECENT_FILE)}")
            time.sleep(delay)
            all_rows = parse_csv(all_txt)
            rep = store_company(db, n, all_rows, {r["slug"] for r in parse_csv(rec_txt)} if rec_txt else set())
            done += 1; new += rep["new_problems"]; rows += rep["problems"]
            log(f"{n}: {rep['problems']} problems ({rep['new_problems']} new)")
        except Exception as e:  # noqa: BLE001  one company failing must not stop the run
            failed += 1; db.rollback(); log(f"{n}: FAILED {e}")
    from app.core import cache
    cache.invalidate("res:")
    return {"companies": done, "failed": failed, "company_problem_rows": rows, "new_problems": new, "source": SOURCE}
