"""Import curated sheets with provenance, ordering, sections, canonical dedupe and a full import report."""
import hashlib
import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, Sheet, SheetItem, SheetSection
from app.models.user import utcnow
from app.services.canonical import canonicalize


def get_or_create_problem(db: Session, url: str, title: str, difficulty: str | None) -> tuple[Problem | None, str]:
    """-> (problem, 'new'|'reused'|'invalid'). Identity = canonical (platform, external_id); never the title."""
    c = canonicalize(url)
    if c is None:
        return None, "invalid"
    platform, ext, canon = c
    p = db.scalar(select(Problem).where(Problem.platform == platform, Problem.external_id == ext))
    if p is not None:
        if p.canonical_url is None:
            p.canonical_url = canon
        if difficulty and not p.source_difficulty:
            p.source_difficulty = difficulty  # first source wins; later sheets don't overwrite
        return p, "reused"
    p = Problem(platform=platform, external_id=ext, name=title, rating=None, tags=[], url=canon, canonical_url=canon,
                source_difficulty=difficulty)
    db.add(p); db.flush()
    return p, "new"


def import_sheet_spec(db: Session, spec: dict, owner_id: int | None = None) -> dict:
    """spec: {slug,title,source_url,license,description,sections:[{name,items:[{url,title,difficulty?}]}], skipped?:[...]}.
    Idempotent by (slug, owner). Order and sections are preserved exactly as given."""
    q = select(Sheet).where(Sheet.slug == spec["slug"], Sheet.owner_id.is_(None) if owner_id is None else Sheet.owner_id == owner_id)
    sheet = db.scalar(q)
    if sheet is None:
        sheet = Sheet(slug=spec["slug"], owner_id=owner_id); db.add(sheet)
    sheet.title, sheet.description = spec["title"], spec.get("description", "")
    sheet.source, sheet.source_url, sheet.license = spec.get("source", ""), spec["source_url"], spec.get("license", "")
    sheet.access_status = spec.get("access_status", "imported")
    db.flush()
    for old in db.scalars(select(SheetItem).where(SheetItem.sheet_id == sheet.id)):
        db.delete(old)
    for old in db.scalars(select(SheetSection).where(SheetSection.sheet_id == sheet.id)):
        db.delete(old)
    db.flush()

    rep = {"items_in_source": 0, "imported": 0, "new_problems": 0, "reused_problems": 0, "duplicates_in_sheet": [],
           "invalid_urls": [], "by_platform": Counter(), "sections": 0, "skipped_no_problem_link": spec.get("skipped", [])}
    seen: set[int] = set()
    pos = 0
    for si, sec in enumerate(spec["sections"]):
        s_row = SheetSection(sheet_id=sheet.id, name=sec["name"], position=si)
        db.add(s_row); db.flush(); rep["sections"] += 1
        for it in sec["items"]:
            rep["items_in_source"] += 1
            prob, kind = get_or_create_problem(db, it["url"], it["title"], it.get("difficulty"))
            if prob is None:
                rep["invalid_urls"].append({"title": it["title"], "url": it["url"]}); continue
            if prob.id in seen:
                rep["duplicates_in_sheet"].append({"title": it["title"], "url": it["url"]}); continue
            seen.add(prob.id)
            db.add(SheetItem(sheet_id=sheet.id, problem_id=prob.id, section=sec["name"], section_id=s_row.id, position=pos,
                             source_title=it["title"], source_difficulty=it.get("difficulty")))
            pos += 1; rep["imported"] += 1
            rep["new_problems" if kind == "new" else "reused_problems"] += 1
            rep["by_platform"][prob.platform] += 1
    rep["by_platform"] = dict(rep["by_platform"])
    sheet.imported_at = utcnow()
    sheet.content_hash = hashlib.sha256(json.dumps(spec["sections"], sort_keys=True).encode()).hexdigest()
    sheet.import_report = rep
    db.commit()
    from app.patterns.mastery import bump_catalog
    bump_catalog()
    return {"sheet_id": sheet.id, "slug": sheet.slug, **rep}
