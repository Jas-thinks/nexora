# Global problem source registry

_Generated 2026-11-19 15:32 UTC. Every seed URL from the acquisition directive appears in `source_matrix.py` (a test fails if one is omitted)._

**42 sources investigated.** 7 have working adapters (codeforces, atcoder, dmoj, codechef, yukicoder, projecteuler, cses; clist written but unverified live).

## Why most sources are not ingested
- **Blocked to automation (HTTP 403)**: LeetCode, SPOJ, beecrowd, Codeforces HTML, CLIST site, Rosalind.
- **robots.txt disallows the data endpoint**: HackerRank `/rest/`, omegaUp `/api/`, Kilonova `/api/`, CodeSignal `/`, CodeUp `/`, AtCoder `/users/*/history/`.
- **Content-Signal restrictions (ai-train=no / ai-input=no)**: Codeforces, DMOJ, Kattis, Toph. Metadata is indexed for search/recommendation only; it is never used to train models, and Toph (ai-input=no) is not ingested at all.
- **Accessible but no API and no adapter yet**: Timus, UVa, USACO, Luogu, HackerEarth, LightOJ, Quera, … (HTML parsers would be needed; rights unclear).
- **Dead or moved**: Aizu judge API (410), Google Coding Competitions (404), Topcoder v5 (404), TLX guess (404).
Each decision is justified per source in platform-capability-matrix.md.

## Reference collections (not problem archives)
- [USACO Guide](https://usaco.guide/) — Repository licence is CC BY-NC-SA 4.0 (non-commercial, share-alike): not ingested; link only.
- [A2OJ](https://a2oj.netlify.app/) — 1.3 KB JS shell; no data endpoint found.
- [KACTL](https://github.com/kth-competitive-programming/kactl) — Algorithm library (code), not a problem set; link only.
- [CP-Algorithms](https://cp-algorithms.com/) — Article site; useful as editorial/reference links per pattern; no structured problem data.
- [Competitive Programmer's Handbook](https://cses.fi/book/book.pdf) — PDF (1.1 MB, HTTP 200). Reference material; link only.

## Curated sheets
See sheet-import-registry.md (imports are separate from canonical problems; memberships preserved).
