import math
import random

from app.services.recommender import estimate_rating, estimate_rating_map


def simulate(true_r, n, seed, spread=500):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        d = int(max(800, min(3500, rng.gauss(true_r, spread))))
        out.append((d, rng.random() < 1 / (1 + math.exp(-(true_r - d) / 200))))
    return out


def test_no_data_returns_floor_and_none_confidence():
    assert estimate_rating_map([]) == (800, "none")


def test_recovers_true_rating_with_enough_data():
    for true_r in (1000, 1500, 2000):
        errs = [abs(estimate_rating_map(simulate(true_r, 150, s))[0] - true_r) for s in range(20)]
        assert sum(errs) / len(errs) <= 150, (true_r, sum(errs) / len(errs))


def test_failures_pull_the_estimate_down_solves_pull_it_up():
    base = [(1200, True)] * 5
    assert estimate_rating_map(base + [(1200, False)] * 20)[0] < estimate_rating_map(base)[0]
    assert estimate_rating_map([(1800, True)] * 5)[0] > estimate_rating_map([(1000, True)] * 5)[0]


def test_lucky_hard_solves_do_not_inflate_like_the_old_estimator():
    honest = simulate(1200, 300, 1)
    lucky = honest + [(2400, True)] * 3  # three lucky/aided hard solves
    new_shift = estimate_rating_map(lucky)[0] - estimate_rating_map(honest)[0]
    old_shift = estimate_rating([d for d, y in lucky if y])[0] - estimate_rating([d for d, y in honest if y])[0]
    assert new_shift <= 100 and old_shift > new_shift  # the max-type statistic moves far more


def test_prior_limits_overconfidence_on_tiny_samples():
    r, conf = estimate_rating_map([(2500, True)])
    assert r < 1700 and conf == "low"  # one solve must not claim 2500


def test_unrated_problems_are_ignored_not_guessed():
    assert estimate_rating_map([(None, True), (None, False)]) == (800, "none")


def test_success_only_data_cannot_exceed_hardest_solve_plus_one_band():
    # self-reported / sheet data logs only successes; the likelihood alone would run away upward
    assert estimate_rating_map([(800, True)] * 10)[0] <= 900
    assert estimate_rating_map([(1000, True)] * 30)[0] <= 1100
