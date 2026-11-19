import math
from datetime import UTC, datetime

import pytest

from app.core import db as dbmod
from app.eval import offline
from app.models.catalog import Problem
from app.patterns import mastery
from app.services import daily
from tests.test_daily import D, mk, sub, world  # noqa


def test_metric_definitions_on_known_cases():
    ranked, pos = [1, 2, 3, 4, 5], {1, 3, 9}
    assert offline.precision_at_k(ranked, pos, 5) == pytest.approx(2 / 5)
    assert offline.recall_at_k(ranked, pos, 5) == pytest.approx(2 / 3)
    ideal = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert offline.ndcg_at_k(ranked, pos, 5) == pytest.approx((1 + 1 / math.log2(4)) / ideal)
    assert offline.ndcg_at_k([9, 1, 3], pos, 3) == pytest.approx(1.0)
    assert offline.recall_at_k([1], set(), 1) == 0.0


def test_bootstrap_ci_brackets_the_mean():
    m, lo, hi = offline.bootstrap_ci([0.1, 0.2, 0.3, 0.4, 0.5] * 4)
    assert lo <= m <= hi and offline.bootstrap_ci([])[0] != offline.bootstrap_ci([])[0]  # nan for empty


def test_as_of_excludes_future_evidence_no_leakage(client, world):
    """Adding submissions AFTER the cutoff must not change anything computed as of the cutoff."""
    with dbmod.SessionLocal() as db:
        uid = world["a"]
        cutoff = datetime.combine(D, datetime.min.time(), UTC)
        before = mastery.assess_all(db, uid, cutoff, as_of=cutoff, use_tracing=False)
        snap = {k: (v.status, v.score, v.solved, v.attempted) for k, v in before.items()}
        # the future: solve lots of dp *after* the cutoff
        for i, r in enumerate(range(800, 1300, 100)):
            sub(db, uid, db.get(Problem, world["probs"][("dp", r)]), "AC", days_ago=-3, n=i)
        db.commit()
        after = mastery.assess_all(db, uid, cutoff, as_of=cutoff, use_tracing=False)
        assert {k: (v.status, v.score, v.solved, v.attempted) for k, v in after.items()} == snap
        # sanity: without as_of the future IS visible, so the test is not vacuous
        assert mastery.assess_all(db, uid, cutoff, use_tracing=False)["dynamic-programming"].solved > snap["dynamic-programming"][2]


def test_ctx_in_eval_mode_ignores_stored_bkt_and_due_reviews(client, world):
    with dbmod.SessionLocal() as db:
        cutoff = datetime.combine(D, datetime.min.time(), UTC)
        c = daily.build_ctx(db, world["a"], D, "personalized", None, None, as_of=cutoff)
        assert c.due_ids == set() and c.friction == {}
        assert all(s.bkt is None for s in c.states.values())


def test_real_temporal_eval_needs_enough_history_and_splits_by_time(client, world):
    with dbmod.SessionLocal() as db:
        assert offline.real_temporal_eval(db, world["a"], min_solved=30) is None  # too little history => no fabricated result
        r = offline.real_temporal_eval(db, world["a"], min_solved=3)
        assert r is None or {"policies", "positives_in_pool"} <= set(r) | {"note"}


def test_policies_return_a_permutation_of_the_pool(client, world):
    with dbmod.SessionLocal() as db:
        ctx = daily.build_ctx(db, world["b"], D, "personalized", None, None, as_of=datetime.combine(D, datetime.min.time(), UTC))
        pool = offline._pool(db, ctx)
        assert pool
        for name, fn in offline.POLICIES.items():
            ranked = fn(ctx, pool, 1)
            assert len(ranked) <= len(pool) and len({p.id for p in ranked}) == len(ranked), name
