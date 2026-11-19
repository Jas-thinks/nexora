"""Holdout experiment on the Daily Challenge: does the personalised policy (treatment) beat a rating-matched baseline (control)?
Assignment is deterministic per user (hash), disclosed in Settings, and opt-out-able. Outcomes come from VERIFIED submissions where possible.
The report refuses to make claims below a minimum sample and always shows intervals."""
import hashlib
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import RecommendationLog, UserPrefs
from app.models.daily import DailyChallenge
from app.models.integrations import Submission
from app.patterns import mastery

MIN_PER_ARM = 30
MATURITY_DAYS = 14


def assign_arm(user_id: int, fraction: float | None = None, salt: str | None = None) -> str:
    s = get_settings()
    f = s.experiment_holdout_fraction if fraction is None else fraction
    h = int(hashlib.sha256(f"{salt or s.experiment_salt}|{user_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "control" if h < f else "treatment"


def arm_for(db: Session, user_id: int) -> tuple[str, bool]:
    """-> (arm, in_analysis). Opted-out users always get the full policy and are excluded from analysis."""
    p = db.get(UserPrefs, user_id)
    if p and p.experiment_opt_out:
        return "treatment", False
    return assign_arm(user_id), True


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4)


def _aw(d):
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _boot_diff(a: list[float], b: list[float], n=2000, seed=3):
    if not a or not b:
        return None
    rng = random.Random(seed)
    ds = sorted(sum(rng.choices(a, k=len(a))) / len(a) - sum(rng.choices(b, k=len(b))) / len(b) for _ in range(n))
    return round(sum(a) / len(a) - sum(b) / len(b), 4), round(ds[int(.025 * n)], 4), round(ds[int(.975 * n)], 4)


def outcomes(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(UTC)
    out = []
    for lg in db.scalars(select(RecommendationLog).where(RecommendationLog.in_analysis.is_(True)).order_by(RecommendationLog.id)):
        at = _aw(lg.created_at)
        ch = db.get(DailyChallenge, lg.challenge_id) if lg.challenge_id else None
        completed = bool(ch and ch.status == "completed")
        fb = (ch.feedback or {}) if ch else {}
        ac = db.scalar(select(Submission.id).where(Submission.user_id == lg.user_id, Submission.problem_id == lg.problem_id, Submission.verdict == "AC",
                                                   Submission.submitted_at >= at.replace(tzinfo=None) if False else Submission.submitted_at >= at).limit(1))
        row = {"arm": lg.arm, "completed": completed, "verified_solved": ac is not None, "hints": fb.get("hints_used"), "matured": now - at >= timedelta(days=MATURITY_DAYS), "delta": None}
        if row["matured"] and lg.pattern:
            before = mastery.assess_all(db, lg.user_id, at, as_of=at, use_tracing=False).get(lg.pattern)
            after = mastery.assess_all(db, lg.user_id, at + timedelta(days=MATURITY_DAYS), as_of=at + timedelta(days=MATURITY_DAYS), use_tracing=False).get(lg.pattern)
            if before and after:
                row["delta"] = round(after.score - before.score, 4)
        out.append(row)
    return out


def report(db: Session, now: datetime | None = None) -> dict:
    rows = outcomes(db, now)
    arms = {}
    for arm in ("treatment", "control"):
        r = [x for x in rows if x["arm"] == arm]
        d = [x["delta"] for x in r if x["delta"] is not None]
        arms[arm] = {"n": len(r), "completion_rate": wilson(sum(x["completed"] for x in r), len(r)), "verified_solve_rate": wilson(sum(x["verified_solved"] for x in r), len(r)),
                     "matured_with_delta": len(d), "mean_pattern_score_delta": round(sum(d) / len(d), 4) if d else None}
    enough = all(arms[a]["n"] >= MIN_PER_ARM for a in arms)
    comp = None
    if enough:
        t = [float(x["verified_solved"]) for x in rows if x["arm"] == "treatment"]
        c = [float(x["verified_solved"]) for x in rows if x["arm"] == "control"]
        td = [x["delta"] for x in rows if x["arm"] == "treatment" and x["delta"] is not None]
        cd = [x["delta"] for x in rows if x["arm"] == "control" and x["delta"] is not None]
        comp = {"verified_solve_rate_diff": _boot_diff(t, c), "pattern_score_delta_diff": _boot_diff(td, cd) if len(td) >= 10 and len(cd) >= 10 else None,
                "note": "(point estimate, 95% bootstrap CI). Treatment minus control."}
    return {"arms": arms, "claims_allowed": enough, "min_per_arm": MIN_PER_ARM, "comparison": comp,
            "message": "Sufficient data to compare arms." if enough else f"Not enough data: need at least {MIN_PER_ARM} recommendations per arm. No effect is claimed.",
            "design": {"assignment": "deterministic hash of user id", "holdout_fraction": get_settings().experiment_holdout_fraction, "control": "rating-matched baseline without weakness/revision/exploration terms",
                       "outcomes": f"completion (self-reported), verified solve (accepted submission after assignment), change in the targeted pattern's mastery score after {MATURITY_DAYS} days (evidence-only, no stored tracing)",
                       "limits": "Observational on users who sync platforms; small samples; self-selection; not a randomised trial unless the hash split is respected."}}
