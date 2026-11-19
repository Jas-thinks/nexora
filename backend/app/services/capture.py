"""Submissions captured by the user's own browser extension.

Trust model: the extension runs in the student's browser, so a student could forge entries. Captured rows are therefore stored with
provenance "extension" ("captured, not verified by the platform"): they feed practice history and mastery like imports do, but never
auto-verify a Daily Challenge (that requires provenance "verified")."""
import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.integrations.registry import BY_SLUG
from app.integrations.types import NormSubmission
from app.models.integrations import ConnectedProfile
from app.services import ingest
from app.services.canonical import canonicalize

VERDICTS = {"accepted": "AC", "wrong answer": "WA", "time limit exceeded": "TLE", "memory limit exceeded": "MLE", "runtime error": "RE", "compile error": "CE", "compilation error": "CE"}
UNJUDGED = {"pending", "judging", "running", "queued", "in queue", "starting"}
MAX_BATCH = 100


def normalise_verdict(raw: str) -> str | None:
    """-> AC/WA/TLE/MLE/RE/CE/OTHER, or None when the submission is not final yet (never guess)."""
    r = (raw or "").strip().lower()
    if not r or r in UNJUDGED:
        return None
    if r in VERDICTS:
        return VERDICTS[r]
    return "RE" if r.startswith("runtime error") else "OTHER"


def parse(platform: str, items: list[dict], now: datetime | None = None) -> tuple[list[NormSubmission], list[dict]]:
    now = now or datetime.now(UTC)
    ok, errors = [], []
    for i, r in enumerate(items[:MAX_BATCH], 1):
        try:
            problem = str(r.get("problem_url") or r.get("problem") or "").strip()
            canon = canonicalize(problem) if problem else None
            if canon is None:
                raise ValueError("problem_url is not a recognised problem URL")
            if canon[0] != platform:
                raise ValueError(f"URL is a {canon[0]} problem but the batch is for {platform}")
            v = normalise_verdict(str(r.get("verdict", "")))
            if v is None:
                raise ValueError("submission is not judged yet")
            at = datetime.fromisoformat(str(r["submitted_at"]).replace("Z", "+00:00"))
            at = at if at.tzinfo else at.replace(tzinfo=UTC)
            if at > now + timedelta(minutes=5):
                raise ValueError("submitted_at is in the future")
            ext = str(r.get("id") or "").strip() or hashlib.sha1(f"{platform}|{canon[1]}|{at.isoformat()}|{v}".encode()).hexdigest()[:16]
            t = r.get("time_ms")
            ok.append(NormSubmission(ext[:80], canon[1], v, str(r.get("verdict", ""))[:60], at, (str(r["language"])[:80] if r.get("language") else None),
                                     int(t) if isinstance(t, (int, float)) and 0 <= t < 10**7 else None, None, None, "extension"))
        except (KeyError, ValueError) as e:
            errors.append({"row": i, "error": f"missing field {e}" if isinstance(e, KeyError) else str(e)})
    if len(items) > MAX_BATCH:
        errors.append({"row": MAX_BATCH + 1, "error": f"batch truncated to {MAX_BATCH} items"})
    return ok, errors


def ingest_batch(db: Session, user_id: int, platform: str, items: list[dict]) -> dict:
    if platform not in BY_SLUG:
        raise ValueError("Unknown platform")
    rows, errors = parse(platform, items)
    p = db.query(ConnectedProfile).filter_by(user_id=user_id, platform=platform).first()
    if p is None:
        p = ConnectedProfile(user_id=user_id, platform=platform, handle="(browser extension)", data_level="user_imported", status="ok")
        db.add(p); db.commit()
    stats = ingest.store_submissions(db, p, rows)
    if rows:
        ingest.refresh_progress_from_submissions(db, user_id)
        from app.services.recommender import rebuild_mastery
        rebuild_mastery(db, user_id)
        from app.services.mistakes import enroll_recovered
        enroll_recovered(db, user_id)
    return {**stats, "rejected": errors[:20], "rejected_count": len(errors), "label": "CAPTURED (from your browser; not verified by the platform)"}
