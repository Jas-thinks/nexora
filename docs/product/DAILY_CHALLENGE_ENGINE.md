# Daily Challenge engine (policy `daily-v1`)

Code: `backend/app/services/daily.py`, `app/patterns/mastery.py`, `app/api/learn.py`. UI: `/daily`.

## Pipeline
`build_ctx` → pool → `score_problem`/`rank` → explanation → persist (weights, features, policy version).

**Context** (per student, per day): pattern states (4-signal mastery), outcomes (verified preferred), MAP rating estimate + confidence, difficulty window, tier, recent patterns (diversity), friction from recent feedback, due reviews, cold-start flag.

**Pool**: unsolved, not recently assigned, mapped to ≥1 pattern. CP mode: CF problems in `[est−100+offset, est+200+offset]`. Interview mode: sheet problems (tier ±1). Personalised: both, plus due reviews. Topic mode: that pattern only. Revision mode: due items only (error if none).

**Objectives** (each 0..1, weighted per mode): weakness, reinforcement, revision, progression (difficulty fit around `est+offset`, reduced where recent challenges felt hard), diversity, exploration. Prerequisite rule: an unexplored pattern whose prerequisites are shaky is penalised ×0.35 (train the prerequisite first). Cold start (<5 solves) re-weights to progression + exploration on easier problems.

**Explanation** is generated from the same numbers: pattern status/score, solved-of-attempted, idle days, rating gap, prerequisite statuses, related solved problems, next patterns, top-3 weighted objectives, evidence list, estimate confidence. No free text from a model.

**Feedback**: solved?, hints used, editorial viewed, self-difficulty, understanding, minutes (only if the student sends it). Effects: `ProblemStatus`, mastery rebuild, Leitner box (1→3→7→21→60 days; failure/aided → box 0), friction (up to −150 rating on that pattern next time).

**Stability/fairness rules**: one challenge per user/day/mode; one swap per day (old problem excluded); a cold-start pick refreshes once evidence arrives; deterministic tie-breaking per (user, day, problem).

## Evidence of behaviour
Unit tests (synthetic fixtures built in-test) prove: weak pattern targeted, different students → different problems/explanations, no solved problems, diversity, cold start gentle, paths shift difficulty, topic/interview constraints, revision, feedback loop, swap, cache invalidation. Live: for a real synced Codeforces profile (2,787 solves) the pick was an FFT problem not touched for 52 days, citing 31 solved problems in that pattern.

## Quality measurement
See docs/recommendation-engine.md. **Result in one line: on a synthetic benchmark the weakness-targeting terms only separate from baselines when histories are long (300 attempts), at a cost in diversity; with short histories nothing is distinguishable. There is no real-user evidence of learning improvement.**

## Not done
Collaborative filtering and learning-to-rank (no interaction data); contextual bandit (no feedback volume); study-time/contest-aware scheduling; global community challenge; Monaco integration; AI post-solve explanation.
