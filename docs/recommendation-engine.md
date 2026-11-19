# Recommendation engine

Two recommenders share one evidence model: the older **practice ladder** (`services/recommender.recommend`) and **Daily Challenge** (`services/daily`, see docs/product/DAILY_CHALLENGE_ENGINE.md).

## Components
- **Rating estimate** (`estimate_rating_map`): MAP of an Elo/IRT-1PL model `P(solve)=σ((r−d)/200)`, prior N(1000, 300²), damped Newton, bucketed by rating. Uses failures as well as solves. **Guard-rail**: never above hardest solve + 100 (failures are often unlogged for self-reports/sheets; without this the likelihood runs away upward). Replaced the original "mean of 5 hardest solves", which the synthetic benchmark showed is inflated by lucky solves as attempts grow.
- **Topic mastery** (`ml/bkt.py` + `rebuild_mastery`): Bayesian Knowledge Tracing per tag, forgetting half-life 60 d, difficulty-adjusted slip/guess; computed by deterministic replay (re-sync cannot double count).
- **Pattern mastery** (`patterns/mastery.py`): coverage .30 + smoothed accuracy .25 + difficulty breadth .20 + tracing .25 → status with explicit thresholds and written reasons.
- **Ranker**: six weighted objectives (weakness, reinforcement, revision, progression, diversity, exploration) + prerequisite penalty; cold-start weights.

## Evaluation (scripts/run_eval.py, app/eval/offline.py)
Metrics: Precision@K, Recall@K, NDCG@K, bootstrap 95% CI, diversity. Leakage control: `as_of` evaluation uses only evidence before the cutoff, ignores the stored BKT table and due reviews (tested: adding future submissions changes nothing).
Baselines: random, rating-matched; ablation: Nexora without weakness/reinforcement/exploration/revision terms.

### REAL temporal split (N = 1 user: a public top-rated Codeforces account used only for smoke testing)
Cutoff at the 80th percentile of first-AC times; 463 candidates; 47 held-out positives in the pool; random expected P = 0.10.
P@10: random 0.10 · rating-matched 0.10 · **Nexora 0.20** · no-weakness 0.10. NDCG@10: 0.110 / 0.095 / 0.158 / 0.069.
**This is one user. It demonstrates the harness works; it is not evidence of quality.** A top-rated user is also unrepresentative of learners.

### SYNTHETIC population (assumed IRT-style students over the real catalog; NOT evidence of learning)
Metrics at K=10, mean [95% bootstrap CI]. History = past attempts per student.

| History / n | Policy | In-ZPD rate | Mean P(solve) | Hits true-weak patterns | Diversity |
|---|---|---|---|---|---|
| 70 / 80 | random | .329 [.295,.364] | .282 | .163 [.131,.196] | .610 |
| | rating-matched | .336 [.289,.384] | .287 | .166 [.134,.200] | .541 |
| | Nexora v1 | .331 [.276,.388] | .292 | .184 [.139,.235] | .534 |
| | Nexora, no weakness terms | .333 [.286,.380] | .297 | .170 [.135,.207] | .616 |
| 300 / 50 | random | .292 [.246,.338] | .282 | .198 [.152,.248] | .650 |
| | rating-matched | .408 [.338,.476] | .338 | .168 [.128,.208] | .548 |
| | Nexora v1 | .372 [.294,.448] | .318 | **.252 [.168,.340]** | .452 |
| | Nexora, no weakness terms | .414 [.350,.480] | .334 | .168 [.120,.218] | .624 |

**Findings.** (1) With short histories no policy is distinguishable. (2) With long histories the weakness terms raise weak-pattern targeting (.252 vs .168 in the ablation) but intervals overlap at n=50, and they cost diversity (.45 vs .62) and a little difficulty fit. (3) The simulator rewards what we built it to reward; it cannot show that students learn faster. (4) The first run exposed an estimator flaw (see above), which was fixed and re-measured.

## Limits and failure modes
Cold start (<5 solves) relies on easy-problem heuristics; sparse per-pattern evidence makes weakness unreliable; unmeasured patterns (35/84) are invisible to the ranker; self-reported data can be wrong; no collaborative signal; the evaluation has no real multi-user ground truth yet. To produce real evidence: log recommendations + outcomes for consenting users and evaluate acceptance/completion and later-performance deltas with a holdout.
