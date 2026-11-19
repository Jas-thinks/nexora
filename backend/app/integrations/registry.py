"""Platform registry: the single source of truth for what each platform can and cannot provide.

Statuses (never overstated):
  integrated    adapter implemented & tested against real response shapes for the listed capabilities
  contests_only adapter provides contest schedule only
  manual_import no usable public API verified; user can import their own export (CSV/JSON)
  link_only     profile link stored; nothing else is fetched
`verified_on` + `evidence` record how a claim was checked. `None` evidence => not investigated yet.
"""
from dataclasses import dataclass

VERIFIED_ON = "2026-11-19"
CAPS = {"profile", "submissions", "rating_history", "contests", "problem_metadata", "manual_import"}


@dataclass(frozen=True)
class PlatformInfo:
    slug: str
    name: str
    url: str
    status: str
    capabilities: frozenset[str] = frozenset()
    api_docs: str | None = None
    auth: str = "none"
    rate_limit: str = "unknown"
    limitations: str = ""
    evidence: str | None = None
    tier: int = 1
    adapter: str | None = None  # key in adapters.ADAPTERS


def P(slug, name, url, status, caps=(), **kw) -> PlatformInfo:
    return PlatformInfo(slug, name, url, status, frozenset(caps), **kw)


_NI = "Not yet investigated. No adapter. Profile link and manual CSV/JSON import only."
_UNVERIFIED = dict(evidence=None, limitations=_NI)

PLATFORMS: list[PlatformInfo] = [
    P("codeforces", "Codeforces", "https://codeforces.com/", "integrated",
      {"profile", "submissions", "rating_history", "contests", "problem_metadata"},
      api_docs="https://codeforces.com/apiHelp", auth="none for public data",
      rate_limit="Official limit: 1 request / 2 s (enforced client-side)",
      limitations="Public submissions only. Contest-time flag derived from participantType. Blog pages block bots (403) and are not used.",
      evidence="Live calls to user.info, user.status, user.rating, contest.list, problemset.problems returned status OK", adapter="codeforces"),
    P("atcoder", "AtCoder", "https://atcoder.jp/", "integrated",
      {"profile", "submissions", "contests", "problem_metadata"},
      api_docs="https://github.com/kenkoooo/AtCoderProblems/blob/master/doc/api.md",
      auth="none", rate_limit="Community API (AtCoder Problems): keep >= 1 request / s",
      limitations="No official AtCoder API. Submissions/problems come from the community-run AtCoder Problems API (may lag). Rating history is NOT available: it lives under /users/*/history/, which atcoder.jp/robots.txt disallows (an earlier version fetched it; removed). Third-party data is labelled as such.",
      evidence="kenkoooo submissions/problems/contests JSON returned 200; atcoder.jp robots.txt disallows /users/*/history/ (verified 2026-11-19)", adapter="atcoder"),
    P("dmoj", "DMOJ", "https://dmoj.ca/", "integrated", {"contests", "problem_metadata"},
      api_docs="https://dmoj.ca/api/v2/", auth="none for problems/contests",
      rate_limit="Not published; 1 request / s used",
      limitations="Per-user submissions need an API token the student must supply: not implemented.",
      evidence="GET /api/v2/problems and /api/v2/contests returned 200 JSON", adapter="dmoj", tier=1),
    P("codechef", "CodeChef", "https://www.codechef.com/", "contests_only", {"contests", "manual_import"},
      api_docs="https://www.codechef.com/api/docs", auth="OAuth app credentials for the official user API (not configured)",
      limitations="Contest list uses the public JSON the site itself serves (undocumented). Official profile/submission API needs OAuth client credentials you must register; not implemented.",
      evidence="GET /api/list/contests/all returned 200 JSON with future_contests", adapter="codechef"),
    P("leetcode", "LeetCode", "https://leetcode.com/", "manual_import", {"manual_import"},
      auth="n/a", limitations="No official public API. The web GraphQL endpoint is undocumented and not used. Import your own submissions as CSV/JSON; problems come from sheet imports.",
      evidence="https://leetcode.com/graphql is undocumented (400 without a query); deliberately not integrated"),
    P("clist", "CLIST (aggregator)", "https://clist.by/", "contests_only", {"contests"},
      api_docs="https://clist.by/api/v4/doc/", auth="Requires the user's own CLIST username + API key (CODEMIND_CLIST_USERNAME/_KEY)",
      limitations="Returns 401 without credentials. Adapter is written to the documented v4 API but NOT verified against a live key (none available); treat as untested.",
      evidence="GET /api/v4/contest/ returned 401 without a key", adapter="clist"),
    P("projecteuler", "Project Euler", "https://projecteuler.net/", "link_only", {"manual_import"},
      limitations="No user API. Public 'minimal' problem list exists; profile progress is not exposed.",
      evidence="https://projecteuler.net/minimal=problems returned 200 text"),
    P("kattis", "Kattis", "https://open.kattis.com/", "link_only", {"manual_import"},
      limitations="No public API verified; robots.txt carries AI/content-signal restrictions. Not scraped.",
      evidence="robots.txt reviewed; HTML only"),
    P("cses", "CSES", "https://cses.fi/problemset/", "link_only", {"manual_import"},
      limitations="No API. Progress requires login; import your own progress.", evidence="HTML only; no robots.txt"),
    P("toph", "Toph", "https://toph.co/", "link_only", {"manual_import"}, limitations="No API verified.", evidence="HTML only"),
    P("topcoder", "Topcoder", "https://www.topcoder.com/", "link_only", {"manual_import"},
      limitations="v5 challenge endpoint tried returned 404; correct public API not verified.", evidence="tried api.topcoder.com/v5/challenges: 404"),
    P("geeksforgeeks", "GeeksforGeeks", "https://www.geeksforgeeks.org/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("hackerrank", "HackerRank", "https://www.hackerrank.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("hackerearth", "HackerEarth", "https://www.hackerearth.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("codesignal", "CodeSignal", "https://codesignal.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("spoj", "SPOJ", "https://www.spoj.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("timus", "Timus Online Judge", "https://acm.timus.ru/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("csacademy", "CSAcademy", "https://csacademy.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("uva", "UVa Online Judge", "https://onlinejudge.org/", "link_only", {"manual_import"}, **_UNVERIFIED),
    P("lightoj", "LightOJ", "https://lightoj.com/", "link_only", {"manual_import"}, **_UNVERIFIED),
    *[P(s, n, u, "link_only", {"manual_import"}, tier=2, **_UNVERIFIED) for s, n, u in [
        ("usaco", "USACO", "https://usaco.org/"), ("usaco-guide", "USACO Guide", "https://usaco.guide/"),
        ("aizu", "Aizu Online Judge", "https://onlinejudge.u-aizu.ac.jp/"), ("yukicoder", "yukicoder", "https://yukicoder.me/"),
        ("luogu", "Luogu", "https://www.luogu.com.cn/"), ("codeup", "CodeUp", "https://codeup.kr/"),
        ("omegaup", "omegaUp", "https://omegaup.com/"), ("beecrowd", "beecrowd", "https://judge.beecrowd.com/"),
        ("tlx", "TLX TOKI", "https://tlx.toki.id/"), ("quera", "Quera", "https://quera.org/"),
        ("eolymp", "Eolymp", "https://eolymp.com/"), ("france-ioi", "France-IOI", "https://www.france-ioi.org/"),
        ("kilonova", "Kilonova", "https://kilonova.ro/"), ("szkopul", "Szkopuł", "https://szkopul.edu.pl/"),
        ("infoarena", "infoarena", "https://infoarena.ro/"), ("neps", "Neps Academy", "https://neps.academy/"),
        ("cf-gym", "Codeforces Gym", "https://codeforces.com/gyms"), ("icpc", "ICPC archives", "https://icpc.global/"),
        ("rosalind", "Rosalind", "https://rosalind.info/")]],
]
BY_SLUG = {p.slug: p for p in PLATFORMS}

DISCOVERY_SOURCES = [
    "https://u.icpc.global/problems/", "https://u.icpc.global/training/", "https://usaco.guide/general/contests",
    "https://icpc.cs.ubc.ca/resources", "https://ancc-iitd.github.io/competitive-programming-resources/",
    "https://sppcontests.org/training/",
]  # Tier 3 leads: not yet crawled; listed so the next investigation pass has a worklist.

DATA_LEVELS = {
    "VERIFIED": "Fetched from the platform's API/public endpoint",
    "PARTIAL": "Some fields unavailable from the source",
    "USER_IMPORTED": "Supplied by the student; not independently verified",
    "UNAVAILABLE": "The source does not expose it (shown as unavailable, never as zero)",
    "ESTIMATED": "Derived by Nexora analytics",
}


def matrix() -> list[dict]:
    return [{
        "slug": p.slug, "name": p.name, "url": p.url, "tier": p.tier, "status": p.status,
        "capabilities": sorted(p.capabilities), "api_docs": p.api_docs, "auth": p.auth,
        "rate_limit": p.rate_limit, "limitations": p.limitations, "evidence": p.evidence,
        "verified_on": VERIFIED_ON if p.evidence else None, "has_adapter": p.adapter is not None,
    } for p in PLATFORMS]
