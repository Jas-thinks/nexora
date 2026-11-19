# Product vision

**NEXORA — AI Engineering Intelligence.** _Think Beyond. Build Beyond._ (Working repository name: Nexora CP Mentor.)

Nexora should understand a student's engineering ability, find the gaps, recommend the next action, supply the tools to practise, and **measure whether the student is actually improving**.

## Principles (these are enforced in code, not slogans)
1. **Evidence over claims.** Every score traces to data (`mastery.PState.reasons`, `Ctx.features`). Unavailable data is shown as unavailable, never zero; unmeasurable patterns are `unmeasured`, never "weak".
2. **Provenance everywhere.** Data is VERIFIED / USER-IMPORTED / LINK-ONLY / ESTIMATED. Self-reported solves never outrank verified submissions.
3. **No fabricated numbers.** Evaluation results are produced by committed scripts and labelled REAL (with N) or SYNTHETIC.
4. **Legitimate sources only.** Official or documented endpoints, MIT-licensed data, user imports. Bot-blocked pages are not bypassed (see sheet registry).
5. **One system, not a feature zoo.** Daily Challenge, Pattern Universe, Visualizer, Explorer and Sheets all read the same canonical problem catalog and mastery model.

## Non-goals (and why)
- Not 36+ micro-pages of patterns written by hand before there is a way to review them; the taxonomy ships as data with relationships, content pages are written progressively.
- Not microservices at launch (see docs/architecture/SCALABILITY_STRATEGY.md for the extraction triggers).
- Not "AI answers" that invent problem statements: problem statements stay on their platforms; Nexora stores metadata and canonical links.
