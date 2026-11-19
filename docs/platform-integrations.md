# Platform integrations

Strategy: official/documented API first → public data endpoints the site itself serves, used politely → user-authorised import → link only. Never bypass auth, anti-bot or ToS; never present partial data as complete. The authoritative status per platform is generated in platform-capability-matrix.md.

## Adapter contract (`integrations/adapters.PlatformAdapter`)
`validate_profile` · `fetch_submissions(handle, checkpoint) → SubmissionPage(items, checkpoint)` · `fetch_rating_history` · `fetch_contests` · `fetch_problem_metadata`. Unsupported capabilities raise `NotSupported` (the job goes `dead`, no retry); nothing is faked. Normalised types: `NormSubmission` (verdict ∈ AC/WA/TLE/MLE/RE/CE/OTHER, `in_contest` tri-state), `NormRating`, `NormContest`, `NormProblem`.

## Verified facts (2026-11-19, live calls)
- **Codeforces** official API: all five capabilities work; limit 1 req/2 s enforced; blog pages return 403 to automation (not used).
- **AtCoder**: no official API. Submissions/problems/contests via the community AtCoder Problems API; rating history via the public profile history JSON (undocumented). Labelled third-party.
- **DMOJ** `/api/v2`: public problems and contests; per-user submissions need a token the student must supply (not implemented).
- **CodeChef**: public contest-list JSON only; official profile API needs OAuth app credentials (not configured).
- **CLIST**: needs the user's own key; implemented to the documented v4 shape but **not verified live**.
- **LeetCode**: no official API; the GraphQL endpoint is undocumented and deliberately unused → manual import.
- **Kattis / CSES / Toph / Project Euler / Topcoder**: HTML-only or unverified; link-only.
- 22 further platforms: **not investigated** (link-only). Tier-3 discovery leads are listed, not crawled.

## Adding a platform
1. Probe the API; record evidence in `registry.py` (status, auth, rate limit, limitations).
2. Implement only the verified capabilities; save trimmed real responses under `tests/fixtures/`.
3. Add adapter tests via `httpx.MockTransport` (shape, incremental checkpoint, error mapping); re-run `scripts/gen_docs.py`.
