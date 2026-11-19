# Analytics metrics (definitions)

| Metric | Definition | Source / provenance |
|---|---|---|
| Estimated rating | MAP ability estimate from (problem rating, solved) outcomes, ≤ hardest solve + 100, rounded to 100; confidence by #outcomes (<10 low, <40 medium) | ESTIMATED; never an official rating |
| Solved | distinct problems with a verified AC or a self-reported solve | VERIFIED when from sync; SELF-REPORTED/USER-IMPORTED otherwise |
| Topic mastery | BKT probability per tag after replaying outcomes with 60-day forgetting | ESTIMATED |
| Pattern status | unexplored / learning / practised / mastered / weak / unmeasured via explicit thresholds on a 4-signal score (see docs/product/DSA_CP_PATTERN_TAXONOMY.md) | ESTIMATED, with written reasons |
| Due for revision | practised/mastered pattern idle > 30 days; Leitner review due dates | derived |
| Link rate | share of submissions linked to a catalog problem | data-quality report |

Rules: unavailable ≠ 0 (unrated problems and tag-less platforms are reported as missing); every number has a source; metrics are recomputable from stored events.
**Not built yet**: rating-history chart, activity/consistency heatmaps, acceptance-rate and difficulty-progression series, learning velocity, recommendation-effectiveness chart, platform-wise breakdown views — although the ingested data supports them.


## Student analytics (implemented: `services/student_analytics.py`, `GET /analytics/me?range=30d|90d|180d|365d|all`, UI `/analytics`)
Every response carries `definitions` (definition + source per metric) and `freshness` (linked profiles, data level, last sync). Unknown stays `null`/"—" (e.g. contest accuracy is withheld unless >=10 submissions have a known in-contest flag; unknown flags are excluded, never counted as practice).
| Metric | Notes |
|---|---|
| Acceptance rate, solved, consistency, streak, first-try rate | definitions in `DEFS`; solved = first AC in range |
| Heatmap | fixed last 365 days, independent of the selected range |
| Weekly timeline | submissions, accepted, acceptance, solved, mean rating of newly solved rated problems (difficulty trend) |
| Rating history per platform | current, peak, volatility (stdev of deltas, >=3), last-5 change, median rank, median performance (only if the platform exposes it) |
| Improvement | first vs second half; verdict only with >=10 submissions per half; descriptive, not causal |
| Topics | strongest/weakest/improving/stagnating, topics need >=5 attempted problems; trend = recent-30d vs prior acceptance |
| Behaviour | abandoned (3+ attempts, never solved, idle >14 d), repeated recent failures, inactivity gaps >7 d |
| Next best action | derived from streak risk, daily challenge status, due reviews, weakest measurable pattern, abandoned problems |
Verified on a real synced profile (378 submissions in 365 d: 76.2% acceptance, "improving", rating 3408 current / 4009 peak). 11 tests use synthetic events to check the maths and the unknown-is-not-zero rules. Gamification (XP/levels/badges/goals/weekly challenge/opt-in leaderboard) is in `services/gamification.py`; its rules are returned by `GET /gamification/me`.
