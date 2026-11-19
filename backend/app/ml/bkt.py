"""Bayesian Knowledge Tracing with forgetting decay.

Per (student, topic) we track P(L): probability the student has mastered the topic.
Standard BKT update on an observed attempt, plus exponential decay toward a prior
when the student has not practised for a while. Interpretable and needs no training
data, which suits the cold-start situation (see docs/architecture/TECHNICAL_DECISIONS.md).
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.2    # prior mastery
    p_learn: float = 0.15  # P(T): learn on an attempt
    p_slip: float = 0.1    # P(S): know it but fail
    p_guess: float = 0.2   # P(G): don't know but succeed
    half_life_days: float = 60.0  # forgetting


def update(p_known: float, correct: bool, params: BKTParams = BKTParams()) -> float:
    s, g, t = params.p_slip, params.p_guess, params.p_learn
    if correct:
        posterior = p_known * (1 - s) / (p_known * (1 - s) + (1 - p_known) * g)
    else:
        posterior = p_known * s / (p_known * s + (1 - p_known) * (1 - g))
    return posterior + (1 - posterior) * t


def decay(p_known: float, days_idle: float, params: BKTParams = BKTParams()) -> float:
    if days_idle <= 0:
        return p_known
    w = math.exp(-math.log(2) * days_idle / params.half_life_days)
    return params.p_init + (p_known - params.p_init) * w


def difficulty_adjusted(params: BKTParams, rating_gap: float) -> BKTParams:
    """Harder problems (positive gap = problem rating above student's) make a
    success more informative (lower guess) and a failure less informative (higher slip)."""
    k = max(-1.0, min(1.0, rating_gap / 800))
    return BKTParams(params.p_init, params.p_learn,
                     p_slip=min(0.4, max(0.02, params.p_slip * (1 + 0.5 * k))),
                     p_guess=min(0.4, max(0.02, params.p_guess * (1 - 0.5 * k))),
                     half_life_days=params.half_life_days)
