import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, Sheet, SheetItem

_ID = re.compile(r"^\d+[A-Za-z]\d?$")
_URL = re.compile(r"codeforces\.com/(?:problemset/problem|contest|gym)/(\d+)(?:/problem)?/([A-Za-z]\d?)")


def parse_ref(ref: str) -> str | None:
    """Accepts '4A', '4/A' or a Codeforces problem URL -> '4A'."""
    ref = ref.strip()
    m = _URL.search(ref)
    if m:
        return f"{m.group(1)}{m.group(2).upper()}"
    ref = ref.replace("/", "")
    return ref.upper() if _ID.match(ref) else None


def import_sheet(db: Session, spec: dict, owner_id: int | None) -> dict:
    """Idempotent by (slug, owner). Unresolvable entries are reported, never invented."""
    sheet = db.scalar(select(Sheet).where(Sheet.slug == spec["slug"], Sheet.owner_id.is_(owner_id) if owner_id is None else Sheet.owner_id == owner_id))
    if sheet is None:
        sheet = Sheet(slug=spec["slug"], owner_id=owner_id)
        db.add(sheet)
    sheet.title, sheet.source, sheet.description = spec["title"], spec.get("source", ""), spec.get("description", "")
    db.flush()
    for old in db.scalars(select(SheetItem).where(SheetItem.sheet_id == sheet.id)):
        db.delete(old)
    missing, seen, pos = [], set(), 0
    for it in spec["items"]:
        ext = parse_ref(it["problem"])
        prob = db.scalar(select(Problem).where(Problem.platform == "codeforces", Problem.external_id == ext)) if ext else None
        if prob is None:
            missing.append(it["problem"]); continue
        if prob.id in seen:
            continue
        seen.add(prob.id)
        db.add(SheetItem(sheet_id=sheet.id, problem_id=prob.id, section=it.get("section", ""), position=pos))
        pos += 1
    db.commit()
    return {"sheet_id": sheet.id, "imported": pos, "missing": missing}
