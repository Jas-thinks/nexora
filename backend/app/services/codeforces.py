"""Codeforces problemset ingestion via the official public API (https://codeforces.com/apiHelp)."""
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.user import utcnow

CF_URL = "https://codeforces.com/api/problemset.problems"


def fetch_problemset(client: httpx.Client | None = None) -> dict:
    c = client or httpx.Client(timeout=30, headers={"User-Agent": "nexora-cp-mentor"})
    r = c.get(CF_URL)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"Codeforces API error: {data.get('comment')}")
    return data


def normalize(raw: dict) -> list[dict]:
    out = []
    for p in raw["result"]["problems"]:
        if p.get("type") not in (None, "PROGRAMMING") or "contestId" not in p:
            continue
        ext = f"{p['contestId']}{p['index']}"
        out.append({
            "platform": "codeforces", "external_id": ext, "name": p["name"],
            "rating": p.get("rating"),  # None => unrated; never guessed
            "tags": sorted(p.get("tags", [])),
            "url": f"https://codeforces.com/problemset/problem/{p['contestId']}/{p['index']}",
        })
    return out


def upsert_problems(db: Session, items: list[dict]) -> dict:
    """Idempotent: safe to re-run; updates changed rows, inserts new ones."""
    existing = {p.external_id: p for p in db.scalars(select(Problem).where(Problem.platform == "codeforces"))}
    added = updated = 0
    for it in items:
        row = existing.get(it["external_id"])
        if row is None:
            db.add(Problem(**it)); added += 1
        elif (row.name, row.rating, row.tags) != (it["name"], it["rating"], it["tags"]):
            row.name, row.rating, row.tags, row.synced_at = it["name"], it["rating"], it["tags"], utcnow()
            updated += 1
    db.commit()
    from app.patterns.mastery import bump_catalog
    bump_catalog()
    return {"added": added, "updated": updated, "total": len(items)}
