"""Offline evaluation of the daily-challenge ranker. Two honest modes:

REAL       temporal split on real synced submission histories. cutoff = 80th percentile of first-AC times; features use
           ONLY evidence before the cutoff (no stored BKT, no future submissions); positives = problems first solved
           after it. Small N; reported with N.
SYNTHETIC  simulated students (latent per-pattern skill) over the REAL catalog. Tests that the policy does what it is
           designed to do under an ASSUMED model. NOT evidence of real learning gains.
"""
import math
import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.integrations import Submission
from app.services import daily


# ---------------------------------------------------------------- metrics
def precision_at_k(ranked: list[int], pos: set[int], k: int) -> float:
    return sum(1 for x in ranked[:k] if x in pos) / k


def recall_at_k(ranked: list[int], pos: set[int], k: int) -> float:
    return sum(1 for x in ranked[:k] if x in pos) / len(pos) if pos else 0.0


def ndcg_at_k(ranked: list[int], pos: set[int], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, x in enumerate(ranked[:k]) if x in pos)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(pos), k)))
    return dcg / ideal if ideal else 0.0


def bootstrap_ci(xs: list[float], n: int = 1000, seed: int = 7) -> tuple[float, float, float]:
    if not xs:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return sum(xs) / len(xs), means[int(.025 * n)], means[int(.975 * n)]


# ---------------------------------------------------------------- policies
def policy_random(ctx, pool, seed):
    r = random.Random(seed); xs = list(pool); r.shuffle(xs); return xs


def policy_rating_matched(ctx, pool, seed):
    return sorted(pool, key=lambda p: (abs((p.rating or 0) - (ctx.est + 100)), p.id))


def policy_nexora(ctx, pool, seed):
    return [p for _, p, _, _ in daily.rank(ctx, pool)]


def policy_no_weakness(ctx, pool, seed):  # ablation: remove the weakness/reinforcement/exploration terms
    saved = dict(ctx.w)
    ctx.w.update(weakness=0.0, reinforcement=0.0, exploration=0.0, revision=0.0)
    try:
        return [p for _, p, _, _ in daily.rank(ctx, pool)]
    finally:
        ctx.w.update(saved)


POLICIES = {"random": policy_random, "rating_matched": policy_rating_matched, "nexora_v1": policy_nexora, "nexora_no_weakness_terms": policy_no_weakness}


def _pool(db: Session, ctx, lo_off=-300, hi_off=700):
    q = select(Problem).where(Problem.platform == "codeforces", Problem.rating.between(max(800, ctx.est + lo_off), ctx.est + hi_off))
    return [p for p in db.scalars(q) if p.id not in ctx.solved_ids and ctx.pmap.get(p.id)]


# ---------------------------------------------------------------- REAL temporal split
def real_temporal_eval(db: Session, user_id: int, ks=(10, 20), min_solved=30) -> dict | None:
    first_ac: dict[int, datetime] = {}
    for pid, at in db.execute(select(Submission.problem_id, Submission.submitted_at).where(
            Submission.user_id == user_id, Submission.platform == "codeforces", Submission.verdict == "AC", Submission.problem_id.is_not(None))
            .order_by(Submission.submitted_at)):
        at = at if at.tzinfo else at.replace(tzinfo=UTC)
        first_ac.setdefault(pid, at)
    if len(first_ac) < min_solved:
        return None
    times = sorted(first_ac.values())
    cutoff = times[int(0.8 * len(times))]
    ctx = daily.build_ctx(db, user_id, cutoff.date(), "personalized", None, None, as_of=cutoff)
    pool = _pool(db, ctx)
    ids = {p.id for p in pool}
    pos = {pid for pid, t in first_ac.items() if t >= cutoff and pid in ids}
    all_future = {pid for pid, t in first_ac.items() if t >= cutoff}
    if not pos:
        return {"user_id": user_id, "n_history": len(times), "n_future": len(all_future), "positives_in_pool": 0, "note": "no held-out positives fall inside the candidate pool"}
    res = {"user_id": user_id, "cutoff": cutoff.isoformat(), "history_solved": len(ctx.solved_ids), "est_rating_at_cutoff": ctx.est,
           "pool_size": len(pool), "held_out_positives": len(all_future), "positives_in_pool": len(pos), "policies": {}}
    for name, fn in POLICIES.items():
        ranked = [p.id for p in fn(ctx, pool, seed=user_id)]
        res["policies"][name] = {f"{m}@{k}": round(f(ranked, pos, k), 4) for k in ks for m, f in (("P", precision_at_k), ("R", recall_at_k), ("NDCG", ndcg_at_k))}
    res["random_expected_P"] = round(len(pos) / len(pool), 5)
    return res


# ---------------------------------------------------------------- SYNTHETIC population
def _sig(x): return 1 / (1 + math.exp(-x))


def synthetic_eval(db: Session, n_students=120, k=10, seed=11, history=70) -> dict:
    """Creates throw-away users/submissions in `db` (use a scratch DB!). Latent skill theta[pattern] ~ N(mu_s, 1)."""
    from app.models.user import User
    from app.patterns import mastery
    rng = random.Random(seed)
    pmap = mastery.problem_patterns(db)
    cat = [p for p in db.scalars(select(Problem).where(Problem.platform == "codeforces", Problem.rating.is_not(None))) if pmap.get(p.id)]
    prim = {p.id: pmap[p.id][0] for p in cat}
    pats = sorted({prim[p.id] for p in cat})
    now = datetime.now(UTC)
    acc = defaultdict(lambda: defaultdict(list))
    for s in range(n_students):
        u = User(email=f"sim{s}@sim.invalid", display_name="sim", password_hash="x"); db.add(u); db.flush()
        mu = rng.gauss(0, 0.7)
        theta = {pt: rng.gauss(mu, 1.0) for pt in pats}
        ability = lambda p: theta[prim[p.id]] - (p.rating - 1100) / 250  # noqa: B023 - used within this iteration only
        # history: "comfort habit" — students gravitate to patterns they are good at, at roughly their own level
        pool = rng.sample(cat, 1500); t = now - timedelta(days=history)
        pool.sort(key=lambda p: -(ability(p) + rng.gauss(0, 1.2)) if abs(ability(p)) < 2 else 9)
        for p in pool[:history]:
            ok = rng.random() < _sig(1.3 * ability(p))
            t += timedelta(hours=7)
            db.add(Submission(user_id=u.id, platform="codeforces", external_id=f"sim{s}-{p.id}", problem_ref=p.external_id, problem_id=p.id,
                              verdict="AC" if ok else "WA", submitted_at=t))
        db.commit()
        as_of = now + timedelta(days=1)
        for name, fn in POLICIES.items():
            ctx = daily.build_ctx(db, u.id, as_of.date(), "personalized", None, None, as_of=as_of)
            cand = _pool(db, ctx, -200, 500)
            top = fn(ctx, cand, seed=s)[:k]
            if not top:
                continue
            ps = [_sig(1.3 * ability(p)) for p in top]
            tracked = sorted(theta, key=theta.get)[:5]  # true 5 weakest patterns
            acc[name]["zpd_hit"].append(sum(0.35 <= x <= 0.85 for x in ps) / len(ps))
            acc[name]["mean_p_solve"].append(sum(ps) / len(ps))
            acc[name]["weak_pattern_hit"].append(sum(prim[p.id] in tracked for p in top) / len(top))
            acc[name]["diversity"].append(len({prim[p.id] for p in top}) / len(top))
    out = {}
    for name, ms in acc.items():
        out[name] = {m: tuple(round(v, 4) for v in bootstrap_ci(xs)) for m, xs in ms.items()}
    return {"n_students": n_students, "k": k, "label": "SYNTHETIC (assumed IRT-style student model; not evidence of real learning)", "policies": out}
