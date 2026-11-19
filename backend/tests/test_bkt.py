import pytest

from app.ml.bkt import BKTParams, decay, difficulty_adjusted, update


def test_success_raises_failure_lowers_relative_to_success():
    p = 0.3
    assert update(p, True) > p
    assert update(p, False) < update(p, True)


def test_monotone_convergence_with_repeated_success():
    p = 0.2
    for _ in range(30):
        nxt = update(p, True)
        assert nxt >= p
        p = nxt
    assert p > 0.95


def test_probabilities_stay_in_unit_interval():
    p = 0.5
    for c in [True, False] * 50:
        p = update(p, c)
        assert 0.0 <= p <= 1.0


def test_decay_moves_toward_prior_and_halves_gap_at_half_life():
    prm = BKTParams()
    p = 0.9
    assert decay(p, 0) == p
    d = decay(p, prm.half_life_days)
    assert d == pytest.approx(prm.p_init + (p - prm.p_init) / 2)
    assert decay(p, 10_000) == pytest.approx(prm.p_init, abs=1e-6)


def test_hard_problem_failure_is_less_damaging_than_easy_problem_failure():
    base = BKTParams()
    hard, easy = difficulty_adjusted(base, 600), difficulty_adjusted(base, -600)
    assert update(0.6, False, hard) > update(0.6, False, easy)
